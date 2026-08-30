"""Tests — la institución bancaria y su búsqueda por BIC.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/res_bank.py``:
``_compute_display_name`` (``:35-39``), ``_search_display_name`` (``:41-48``),
la normalización del BIC de ``create``/``write`` (``:50-60``), y los dos
``onchange`` de país y estado (``:62-70``).

Qué haría fallar a cada control se declara en su caso.
"""
import pytest

from addons.base.models import ResBank, ResCountry, ResCountryState
from tests.conftest import matching_by_display_name

pytestmark = pytest.mark.integration


@pytest.fixture
def geography(db):
    """Dos países con un estado cada uno.

    Se usa ``get_or_create``: la base de QA es compartida y ya trae países
    sembrados, así que un ``create`` pelado revienta con la única de ``code``.
    """
    mx, _ = ResCountry.objects.get_or_create(
        code='MX', defaults={'name': 'México'})
    fr, _ = ResCountry.objects.get_or_create(
        code='FR', defaults={'name': 'Francia'})
    jalisco, _ = ResCountryState.objects.get_or_create(
        country=mx, code='JAL', defaults={'name': 'Jalisco'})
    bretana, _ = ResCountryState.objects.get_or_create(
        country=fr, code='BRE', defaults={'name': 'Bretaña'})
    return {'mx': mx, 'fr': fr, 'jalisco': jalisco, 'bretana': bretana}


class TestDisplayName:
    """≙ ``_compute_display_name`` (``odoo19c: res_bank.py:35-39``)."""

    def test_the_bic_is_appended_when_present(self, db):
        bank = ResBank(name='BBVA', bic='BCMRMXMM')
        assert bank._compute_display_name() == 'BBVA - BCMRMXMM'
        assert str(bank) == 'BBVA - BCMRMXMM'

    def test_without_a_bic_only_the_name_shows(self, db):
        """CONTROL de la dirección contraria: sin él, un formato que SIEMPRE
        pegara el separador pasaría el caso anterior y dejaría 'BBVA - '.
        """
        bank = ResBank(name='BBVA', bic='')
        assert bank._compute_display_name() == 'BBVA'
        assert ' - ' not in str(bank)


class TestBicIsUppercased:
    """La normalización de ``create``/``write`` (``odoo19c: res_bank.py:50-60``)."""

    def test_a_lowercase_bic_is_stored_uppercase(self, db):
        bank = ResBank.objects.create(name='BBVA', bic='bcmrmxmm')
        bank.refresh_from_db()
        assert bank.bic == 'BCMRMXMM'

    def test_it_normalises_on_update_too(self, db):
        """La fuente lo hace en sus DOS entradas de escritura.

        Aquí las dos son ``save()``, y este caso es el que lo comprueba: sin
        él, una normalización puesta sólo en el alta pasaría el caso anterior.
        """
        bank = ResBank.objects.create(name='BBVA', bic='BCMRMXMM')
        bank.bic = 'nafxmxmm'
        bank.save()
        bank.refresh_from_db()
        assert bank.bic == 'NAFXMXMM'

    def test_an_empty_bic_survives_as_empty(self, db):
        """``''.upper()`` es ``''``, pero la guarda de la fuente corta antes.

        El caso fija que un banco sin BIC no adquiere uno: sin la guarda, un
        ``None`` reventaría con ``AttributeError`` en vez de guardarse.
        """
        bank = ResBank.objects.create(name='Banco sin BIC', bic='')
        bank.refresh_from_db()
        assert bank.bic == ''


class TestSearchDisplayName:
    """≙ ``_search_display_name`` (``odoo19c: res_bank.py:41-48``)."""

    @pytest.fixture
    def banks(self, db):
        return {
            'bbva':  ResBank.objects.create(name='BBVA', bic='BCMRMXMM'),
            'banorte': ResBank.objects.create(name='Banorte', bic='MENOMXMT'),
        }

    def test_the_name_matches_by_content(self, banks):
        found = matching_by_display_name(ResBank, 'ilike', 'orte')
        assert list(found) == [banks['banorte']]

    def test_the_bic_matches_by_prefix(self, banks):
        found = matching_by_display_name(ResBank, 'ilike', 'BCMR')
        assert list(found) == [banks['bbva']]

    def test_the_bic_does_not_match_in_the_middle(self, banks):
        """La asimetría entera del método, y el caso que la fija.

        Un BIC se teclea desde el principio; compararlo por contenido
        devolvería bancos cuyo código lleva la cadena en medio. Sin este caso,
        un ``icontains`` en las dos columnas pasaría los dos anteriores.
        """
        assert not matching_by_display_name(ResBank, 'ilike', 'RMXMM')

    def test_not_ilike_returns_the_complement(self, banks):
        found = matching_by_display_name(ResBank, 'not ilike', 'BCMR')
        assert banks['bbva'] not in found
        assert banks['banorte'] in found

    def test_an_empty_value_matches_everything(self, banks):
        """La fuente delega en ``super()`` cuando el valor es falso."""
        found = matching_by_display_name(ResBank, 'ilike', '')
        assert banks['bbva'] in found and banks['banorte'] in found


class TestOnchangeCountryAndState:
    """≙ los dos ``onchange`` (``odoo19c: res_bank.py:62-70``)."""

    def test_changing_the_country_clears_a_state_of_another_one(self, geography):
        bank = ResBank(name='BBVA', country=geography['fr'],
                       state=geography['jalisco'])
        bank._onchange_country_id()
        assert bank.state is None

    def test_a_state_of_the_same_country_survives(self, geography):
        """CONTROL de la dirección contraria: sin él, un onchange que borrara
        SIEMPRE el estado pasaría el caso anterior.
        """
        bank = ResBank(name='BBVA', country=geography['mx'],
                       state=geography['jalisco'])
        bank._onchange_country_id()
        assert bank.state == geography['jalisco']

    def test_choosing_a_state_sets_its_country(self, geography):
        bank = ResBank(name='BBVA', country=geography['fr'])
        bank.state = geography['jalisco']
        bank._onchange_state()
        assert bank.country == geography['mx']

    def test_without_a_state_the_country_is_untouched(self, geography):
        bank = ResBank(name='BBVA', country=geography['fr'])
        bank._onchange_state()
        assert bank.country == geography['fr']


class TestClassAttributes:
    """``atributos-de-clase-de-modelo.md``: los cuatro que la fuente declara."""

    def test_the_four_attributes_of_the_source_are_declared(self):
        assert ResBank._name == 'res.bank'
        assert ResBank._description == 'Bank'
        assert ResBank._order == 'name, id'
        assert ResBank._rec_names_search == ['name', 'bic']

    def test_the_table_matches_the_dotted_name(self):
        """Lo que ``orm.registry.check_table_matches_name()`` verifica."""
        assert ResBank._meta.db_table == ResBank._name.replace('.', '_')

    def test_no_char_carries_an_invented_cap(self):
        """La fuente los declara sin tamaño; aquí tampoco.

        Sin este caso, reintroducir un tope en cualquiera de los seis pasaría
        inadvertido — que es exactamente cómo llegaron.
        """
        capped = [field.name for field in ResBank._meta.get_fields()
                  if getattr(field, 'max_length', None)]
        assert capped == [], f'topes inventados: {capped}'
