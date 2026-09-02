"""``base_address_extended`` — los símbolos que la fuente cuelga de ``res.partner``.

``_address_fields`` (``odoo19c: base_address_extended/models/res_partner.py:20``),
``_onchange_city_id`` (``:47``), ``_onchange_country_id`` (``:58``),
``_get_res_city_by_name`` (``:64``), los tres de la calle (``:24``, ``:32``,
``:39``) y ``ResCity._compute_display_name`` (``res_city.py:17``).

Todos tienen por receptor ``base.ResPartner``, que es donde la fuente los
declara. El almacén difiere —``city_id`` y las tres partes viven en el RELATED
``AddressStructured`` (DEC-SALE-01)— y esa travesía es justo lo que estos casos
fijan.
"""
import pytest

from addons.base.models import ResCountry, ResCountryState, ResPartner
from addons.base_address_extended.models import AddressStructured, ResCity

pytestmark = pytest.mark.django_db


@pytest.fixture
def mexico():
    """México, tomado si ya existe.

    ``res.country`` se siembra por migración de datos y ``code`` es único, así
    que un ``create`` choca con ``res_country_code_key``. El idioma del árbol
    para esto es ``get_or_create`` sobre el código — el mismo que usa el
    archivo hermano ``test_base_address_extended.py``.
    """
    return ResCountry.objects.get_or_create(
        code='MX', defaults={'name': 'México'})[0]


@pytest.fixture
def jalisco(mexico):
    return ResCountryState.objects.create(
        country=mexico, name='Jalisco', code='JAL')


@pytest.fixture
def guadalajara(mexico, jalisco):
    return ResCity.objects.create(
        name='Guadalajara', zipcode='44100', country_id=mexico,
        state_id=jalisco)


class TestAddressFields:
    """``_address_fields`` — ≙ ``super()._address_fields() + ['city_id']``."""

    def test_city_id_is_appended_to_the_base_list(self):
        campos = ResPartner._address_fields()
        assert 'city_id' in campos

    def test_the_six_fields_of_base_survive(self):
        """ACUMULA: el terminal de ``base`` conserva los suyos."""
        campos = ResPartner._address_fields()
        for esperado in ('street', 'street2', 'zip', 'city', 'state',
                         'country'):
            assert esperado in campos

    def test_city_id_goes_last_like_the_source(self):
        """La fuente escribe ``super() + ['city_id']``: el suyo va detrás."""
        assert ResPartner._address_fields()[-1] == 'city_id'

    def test_every_address_field_is_readable_on_a_partner(self):
        """El consumidor real: ``_prepare_address_values`` hace ``getattr``.

        Es el caso que destapó que ``city_id`` tenía que existir sobre
        ``ResPartner`` y no sólo sobre el RELATED.
        """
        partner = ResPartner.objects.create(name='Ferretería Los Arcos')
        for field_name in ResPartner._address_fields():
            getattr(partner, field_name)


class TestCityIdSurface:
    """``city_id`` — columna de ``res.partner`` allá, propiedad aquí."""

    def test_reading_city_id_without_a_structured_row_gives_none(self):
        partner = ResPartner.objects.create(name='Papelería El Lápiz')
        assert partner.city_id is None

    def test_writing_city_id_creates_the_structured_row(self, guadalajara):
        partner = ResPartner.objects.create(name='Óptica La Luz')
        partner.city_id = guadalajara

        assert partner.city_id == guadalajara
        assert AddressStructured.objects.filter(partner=partner).exists()


class TestOnchangeCityId:
    """``_onchange_city_id`` — ≙ ``:47-56``."""

    def test_choosing_a_city_copies_name_zip_and_state(self, guadalajara):
        partner = ResPartner.objects.create(name='Taquería El Buen Pastor')
        partner.city_id = guadalajara

        partner._onchange_city_id()

        assert partner.city == 'Guadalajara'
        assert partner.zip == '44100'
        assert partner.state == guadalajara.state_id

    def test_clearing_the_city_clears_the_three_on_a_saved_partner(
            self, guadalajara):
        """La rama ``elif self._origin`` de la fuente — aquí ``self.pk``."""
        partner = ResPartner.objects.create(name='Zapatería El Andar')
        partner.city_id = guadalajara
        partner._onchange_city_id()

        partner.city_id = None
        partner._onchange_city_id()

        assert partner.city == ''
        assert partner.zip == ''
        assert partner.state is None


class TestOnchangeCountryId:
    """``_onchange_country_id`` — ≙ ``:58-62``, con el ``super()`` delante."""

    def test_changing_country_drops_a_city_of_another_country(
            self, guadalajara):
        otro = ResCountry.objects.get_or_create(
            code='GT', defaults={'name': 'Guatemala'})[0]
        partner = ResPartner.objects.create(name='Café La Ceiba')
        partner.city_id = guadalajara
        partner.country = otro

        partner._onchange_country_id()

        assert partner.city_id is None

    def test_a_city_of_the_same_country_is_kept(self, mexico, guadalajara):
        partner = ResPartner.objects.create(name='Librería Sor Juana')
        partner.city_id = guadalajara
        partner.country = mexico

        partner._onchange_country_id()

        assert partner.city_id == guadalajara

    def test_the_previous_implementation_still_runs(self, mexico, jalisco):
        """El ``super()`` de la fuente: ``base`` invalida el estado ajeno.

        Discrimina el ``wrap_method`` de un ``chain_method``: si este override
        no invocara ``previous()``, el estado de otro país sobreviviría.
        """
        otro = ResCountry.objects.get_or_create(
            code='BZ', defaults={'name': 'Belice'})[0]
        partner = ResPartner.objects.create(name='Hotel Río Hondo')
        partner.state = jalisco
        partner.country = otro

        partner._onchange_country_id()

        assert partner.state is None


class TestGetResCityByName:
    """``_get_res_city_by_name`` — ≙ ``:64-76``."""

    def test_finds_the_city_ignoring_case(self, mexico, guadalajara):
        assert ResPartner._get_res_city_by_name(
            'guadalajara', mexico) == guadalajara

    def test_returns_none_without_a_name(self, mexico):
        assert ResPartner._get_res_city_by_name('', mexico) is None

    def test_returns_none_without_a_country(self):
        assert ResPartner._get_res_city_by_name('Guadalajara', None) is None

    def test_does_not_cross_country_borders(self, guadalajara):
        otro = ResCountry.objects.get_or_create(
            code='HN', defaults={'name': 'Honduras'})[0]
        assert ResPartner._get_res_city_by_name('Guadalajara', otro) is None


class TestStreetOnPartner:
    """Los tres de la calle, con el receptor de la fuente."""

    def _with_structured(self, name='Av. Insurgentes Sur 1234 - 5B'):
        partner = ResPartner.objects.create(name='Mueblería El Roble',
                                            street=name)
        AddressStructured.objects.create(partner=partner)
        partner.refresh_from_db()
        return partner

    def test_compute_street_data_splits_into_the_related_row(self):
        partner = self._with_structured()
        partner._compute_street_data()

        assert partner.structured.street_name == 'Av. Insurgentes Sur'
        assert partner.structured.street_number == '1234'
        assert partner.structured.street_number2 == '5B'

    def test_inverse_street_data_recomposes_the_street(self):
        partner = self._with_structured()
        partner._compute_street_data()

        assert (partner._inverse_street_data()
                == 'Av. Insurgentes Sur 1234 - 5B')

    def test_get_street_split_returns_the_stored_parts(self):
        partner = self._with_structured()
        partner._compute_street_data()

        assert partner._get_street_split() == {
            'street_name': 'Av. Insurgentes Sur',
            'street_number': '1234',
            'street_number2': '5B',
        }

    def test_get_street_split_falls_back_to_base_without_a_related_row(self):
        """El relevo por ``None``: sin fila RELATED gana el de ``base``.

        ``base.ResPartner._get_street_split`` parte la calle al vuelo, así que
        devuelve las tres claves igual — no ``None``.
        """
        partner = ResPartner.objects.create(name='Vidriería La Esquina',
                                            street='Calle Falsa 123')
        partido = partner._get_street_split()

        assert set(partido) == {'street_name', 'street_number',
                                'street_number2'}


class TestResCityDisplayName:
    """``_compute_display_name`` — ≙ ``res_city.py:17-21``."""

    def test_zipcode_is_appended_in_parentheses(self, guadalajara):
        assert guadalajara._compute_display_name() == 'Guadalajara (44100)'

    def test_without_zipcode_only_the_name(self, mexico):
        city = ResCity.objects.create(name='Tepoztlán', country_id=mexico)
        assert city._compute_display_name() == 'Tepoztlán'

    def test_str_delegates_to_the_compute(self, guadalajara):
        assert str(guadalajara) == guadalajara._compute_display_name()
