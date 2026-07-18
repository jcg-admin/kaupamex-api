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

from addons.base.models import ResCountry, ResCountryState
from addons.base_address_extended.models import CountryAddressPolicy, ResCity
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
