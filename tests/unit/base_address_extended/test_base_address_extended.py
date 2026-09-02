"""Contrato de ``base_address_extended`` — ``ResCity`` / ``CountryAddressPolicy``
+ ``street_split``.

Portación fiel del addon ``base_address_extended`` de Odoo (18/19). Cada test
verifica un comportamiento del original:

- ``street_split`` byte-idéntico a ``odoo.tools.misc.street_split`` (regex
  ``ADDRESS_REGEX``): descompone la calle en name/number/number2.
- ``ResCity.__str__`` == ``_compute_display_name`` de Odoo (``name`` o
  ``name (zipcode)``).
- ``ResCity.country_id`` requerido; ``state_id`` opcional.
- ``CountryAddressPolicy`` OneToOne (RELATED de ``enforce_cities``, DEC-SALE-01).
"""
import pytest

from addons.base.models import ResCountry, ResCountryState, ResPartner
from addons.base_address_extended.models import (
    AddressStructured,
    CountryAddressPolicy,
    ResCity,
)
from addons.base_address_extended.services import street_split


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
    def test_street_split_matches_reference(self, street, expected):
        assert street_split(street) == expected

    def test_street_number_with_letters(self):
        # '12B' es un número que arranca con dígito (Odoo lo captura entero).
        assert street_split('Main 12B')['street_number'] == '12B'


pytestmark = pytest.mark.django_db


class TestResCity:
    def test_str_without_zipcode(self):
        mx = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'México'})[0]
        c = ResCity.objects.create(name='Guadalajara', country_id=mx)
        assert str(c) == 'Guadalajara'

    def test_str_with_zipcode(self):
        mx = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'México'})[0]
        c = ResCity.objects.create(name='Guadalajara', country_id=mx, zipcode='44100')
        assert str(c) == 'Guadalajara (44100)'

    def test_country_required_state_optional(self):
        mx = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'México'})[0]
        jal = ResCountryState.objects.create(country=mx, name='Jalisco', code='JAL')
        c = ResCity.objects.create(name='Zapopan', country_id=mx, state_id=jal)
        assert c.state_id == jal
        c2 = ResCity.objects.create(name='Tlaquepaque', country_id=mx)
        assert c2.state_id is None

    def test_state_set_null_on_delete(self):
        mx = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'México'})[0]
        jal = ResCountryState.objects.create(country=mx, name='Jalisco', code='JAL')
        c = ResCity.objects.create(name='Zapopan', country_id=mx, state_id=jal)
        jal.delete()
        c.refresh_from_db()
        assert c.state_id is None
        assert ResCity.objects.filter(pk=c.pk).exists()

    def test_cities_reverse_on_country(self):
        mx = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'México'})[0]
        ResCity.objects.create(name='Guadalajara', country_id=mx)
        ResCity.objects.create(name='Monterrey', country_id=mx)
        assert mx.cities.count() == 2


class TestCountryAddressPolicy:
    def test_enforce_cities_defaults_false(self):
        mx = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'México'})[0]
        pol = CountryAddressPolicy.objects.create(country=mx)
        assert pol.enforce_cities is False

    def test_one_to_one_country(self):
        mx = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'México'})[0]
        CountryAddressPolicy.objects.create(country=mx, enforce_cities=True)
        assert mx.address_policy.enforce_cities is True

    def test_cascade_delete_with_country(self):
        mx = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'México'})[0]
        CountryAddressPolicy.objects.create(country=mx)
        mx.delete()
        assert CountryAddressPolicy.objects.count() == 0


def _make_partner(street='Av. Insurgentes Sur 1234 - 5B'):
    # En la referencia una dirección ES un partner: el addon extiende
    # ``res.partner``, no una tabla de direcciones aparte
    # (odoo19c: base_address_extended/models/res_partner.py).
    return ResPartner.objects.create(
        name='Nestor', street=street, city='CDMX', zip='03100',
        phone='5512345678',
    )


class TestAddressStructured:
    def test_compute_street_data_splits_parts(self):
        partner = _make_partner()
        st = AddressStructured(partner=partner)
        st._compute_street_data(partner.street)
        assert st.street_name == 'Av. Insurgentes Sur'
        assert st.street_number == '1234'
        assert st.street_number2 == '5B'

    def test_inverse_street_data_roundtrip(self):
        partner = _make_partner()
        st = AddressStructured(partner=partner)
        st._compute_street_data(partner.street)
        # Odoo _inverse_street_data: 'name number - number2'.
        assert st._inverse_street_data() == 'Av. Insurgentes Sur 1234 - 5B'

    def test_get_street_split_returns_three_keys(self):
        partner = _make_partner('Main 12')
        st = AddressStructured(partner=partner)
        st._compute_street_data(partner.street)
        assert st._get_street_split() == {
            'street_name': 'Main', 'street_number': '12', 'street_number2': '',
        }

    def test_one_to_one_reverse_on_partner(self):
        partner = _make_partner()
        AddressStructured.objects.create(partner=partner, street_name='Main')
        partner.refresh_from_db()
        assert partner.structured.street_name == 'Main'

    def test_country_enforce_cities_false_without_city(self):
        partner = _make_partner()
        st = AddressStructured.objects.create(partner=partner)
        assert st.country_enforce_cities is False

    def test_country_enforce_cities_reads_policy(self):
        mx = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'México'})[0]
        CountryAddressPolicy.objects.create(country=mx, enforce_cities=True)
        city = ResCity.objects.create(name='CDMX', country_id=mx)
        partner = _make_partner()
        st = AddressStructured.objects.create(partner=partner, city_id=city)
        assert st.country_enforce_cities is True

    def test_archiving_partner_keeps_structured_row(self):
        # ``res.partner`` NO se borra lógicamente: se **archiva** con
        # ``active`` (odoo19c: base/models/res_partner.py, campo ``active``).
        # Archivar no toca la BD → la fila estructurada persiste. Reemplaza al
        # test de soft-delete, que asumía el ``users.Address`` disuelto.
        partner = _make_partner()
        AddressStructured.objects.create(partner=partner)
        partner.active = False
        partner.save(update_fields=['active'])
        assert AddressStructured.objects.count() == 1

    def test_delete_cascades_structured_row(self):
        # ``delete()`` en ResPartner sí borra la fila → CASCADE elimina la
        # AddressStructured enlazada (on_delete=CASCADE en el OneToOne).
        partner = _make_partner()
        AddressStructured.objects.create(partner=partner)
        partner.delete()
        assert AddressStructured.objects.count() == 0
