"""Contrato de ``base_address_extended`` — ``ResCity`` / ``CountryAddressPolicy``
+ ``street_split``.

Portación fiel del addon ``base_address_extended`` de Odoo (18/19). Cada test
verifica un comportamiento del original:

- ``street_split`` byte-idéntico a ``odoo.tools.misc.street_split`` (regex
  ``ADDRESS_REGEX``): descompone la calle en name/number/number2.
- ``ResCity.__str__`` == ``_compute_display_name`` de Odoo (``name`` o
  ``name (zipcode)``).
- ``ResCity.country`` requerido; ``state`` opcional.
- ``CountryAddressPolicy`` OneToOne (RELATED de ``enforce_cities``, DEC-SALE-01).
"""
import pytest

from django.contrib.auth import get_user_model

from addons.base.models import ResCountry, ResCountryState
from addons.base_address_extended.models import (
    AddressStructured,
    CountryAddressPolicy,
    ResCity,
)
from addons.base_address_extended.services import street_split
from addons.users.models import Address

User = get_user_model()


class TestStreetSplit:
    # Fiel a odoo.tools.street_split: (street) -> {name, number, number2}.
    @pytest.mark.parametrize('street,expected', [
        ('Rue des Bouchers 12',
         {'street_name': 'Rue des Bouchers', 'street_number': '12', 'street_number2': ''}),
        ('Av. Insurgentes Sur 1234 - 5B',
         {'street_name': 'Av. Insurgentes Sur', 'street_number': '1234', 'street_number2': '5B'}),
        ('Calle sin numero',
         {'street_name': 'Calle sin numero', 'street_number': '', 'street_number2': ''}),
        ('', {'street_name': '', 'street_number': '', 'street_number2': ''}),
        (None, {'street_name': '', 'street_number': '', 'street_number2': ''}),
    ])
    def test_street_split_matches_odoo(self, street, expected):
        assert street_split(street) == expected

    def test_street_number_with_letters(self):
        # '12B' es un número que arranca con dígito (Odoo lo captura entero).
        assert street_split('Main 12B')['street_number'] == '12B'


pytestmark = pytest.mark.django_db


class TestResCity:
    def test_str_without_zipcode(self):
        mx = ResCountry.objects.create(name='México', code='MX')
        c = ResCity.objects.create(name='Guadalajara', country=mx)
        assert str(c) == 'Guadalajara'

    def test_str_with_zipcode(self):
        mx = ResCountry.objects.create(name='México', code='MX')
        c = ResCity.objects.create(name='Guadalajara', country=mx, zipcode='44100')
        assert str(c) == 'Guadalajara (44100)'

    def test_country_required_state_optional(self):
        mx = ResCountry.objects.create(name='México', code='MX')
        jal = ResCountryState.objects.create(country=mx, name='Jalisco', code='JAL')
        c = ResCity.objects.create(name='Zapopan', country=mx, state=jal)
        assert c.state == jal
        c2 = ResCity.objects.create(name='Tlaquepaque', country=mx)
        assert c2.state is None

    def test_state_set_null_on_delete(self):
        mx = ResCountry.objects.create(name='México', code='MX')
        jal = ResCountryState.objects.create(country=mx, name='Jalisco', code='JAL')
        c = ResCity.objects.create(name='Zapopan', country=mx, state=jal)
        jal.delete()
        c.refresh_from_db()
        assert c.state is None
        assert ResCity.objects.filter(pk=c.pk).exists()

    def test_cities_reverse_on_country(self):
        mx = ResCountry.objects.create(name='México', code='MX')
        ResCity.objects.create(name='Guadalajara', country=mx)
        ResCity.objects.create(name='Monterrey', country=mx)
        assert mx.cities.count() == 2


class TestCountryAddressPolicy:
    def test_enforce_cities_defaults_false(self):
        mx = ResCountry.objects.create(name='México', code='MX')
        pol = CountryAddressPolicy.objects.create(country=mx)
        assert pol.enforce_cities is False

    def test_one_to_one_country(self):
        mx = ResCountry.objects.create(name='México', code='MX')
        CountryAddressPolicy.objects.create(country=mx, enforce_cities=True)
        assert mx.address_policy.enforce_cities is True

    def test_cascade_delete_with_country(self):
        mx = ResCountry.objects.create(name='México', code='MX')
        CountryAddressPolicy.objects.create(country=mx)
        mx.delete()
        assert CountryAddressPolicy.objects.count() == 0


def _make_address(street='Av. Insurgentes Sur 1234 - 5B'):
    user = User.objects.create_user(email='addr@example.com', password='x')
    return Address.objects.create(
        user=user, recipient_name='Nestor', street=street, city='CDMX',
        state='CDMX', zip_code='03100', phone='5512345678',
    )


class TestAddressStructured:
    def test_compute_from_street_splits_parts(self):
        addr = _make_address()
        st = AddressStructured(address=addr)
        st.compute_from_street(addr.street)
        assert st.street_name == 'Av. Insurgentes Sur'
        assert st.street_number == '1234'
        assert st.street_number2 == '5B'

    def test_inverse_to_street_roundtrip(self):
        addr = _make_address()
        st = AddressStructured(address=addr)
        st.compute_from_street(addr.street)
        # Odoo _inverse_street_data: 'name number - number2'.
        assert st.inverse_to_street() == 'Av. Insurgentes Sur 1234 - 5B'

    def test_get_street_split_returns_three_keys(self):
        addr = _make_address('Main 12')
        st = AddressStructured(address=addr)
        st.compute_from_street(addr.street)
        assert st.get_street_split() == {
            'street_name': 'Main', 'street_number': '12', 'street_number2': '',
        }

    def test_one_to_one_reverse_on_address(self):
        addr = _make_address()
        AddressStructured.objects.create(address=addr, street_name='Main')
        addr.refresh_from_db()
        assert addr.structured.street_name == 'Main'

    def test_country_enforce_cities_false_without_city(self):
        addr = _make_address()
        st = AddressStructured.objects.create(address=addr)
        assert st.country_enforce_cities is False

    def test_country_enforce_cities_reads_policy(self):
        mx = ResCountry.objects.create(name='México', code='MX')
        CountryAddressPolicy.objects.create(country=mx, enforce_cities=True)
        city = ResCity.objects.create(name='CDMX', country=mx)
        addr = _make_address()
        st = AddressStructured.objects.create(address=addr, city=city)
        assert st.country_enforce_cities is True

    def test_soft_delete_keeps_structured_row(self):
        # Address hereda SoftDeleteModel: delete() es soft (marca is_deleted),
        # NO dispara el CASCADE de la BD → la fila estructurada persiste.
        addr = _make_address()
        AddressStructured.objects.create(address=addr)
        addr.delete()
        assert AddressStructured.objects.count() == 1

    def test_hard_delete_cascades_structured_row(self):
        # hard_delete() sí borra la fila de la BD → CASCADE elimina la
        # AddressStructured enlazada.
        addr = _make_address()
        AddressStructured.objects.create(address=addr)
        addr.hard_delete()
        assert AddressStructured.objects.count() == 0
