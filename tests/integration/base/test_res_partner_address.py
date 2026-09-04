"""Tests — el bloque de dirección de ``res.partner``.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/res_partner.py``:
``_get_street_split`` (``:331``), ``_get_default_address_format`` (``:1170``),
``_get_address_format`` (``:1174``), ``_prepare_display_address`` (``:1177``),
``_display_address`` (``:1196``), ``_display_address_depends`` (``:1209``),
``_get_country_name`` (``:1242``), ``_get_all_addr`` (``:1245``) y
``address_get`` (``:1121``); más ``tools.street_split``
(``odoo19c: odoo/tools/misc.py:1914``).

Por qué el formato lo pone el PAÍS y no el código
==================================================

La fuente formatea la dirección **según las costumbres del país al que
pertenece**: el ``address_format`` de ``res.country`` es una plantilla de
``%(campo)s`` y el partner sólo la rellena. Un formateador cableado en Python
—«calle, ciudad, CP»— es correcto en México y falso en Japón, donde el orden se
invierte, y el error no se ve hasta que hay un cliente allá.

``address_get`` es una búsqueda, no un getter
==============================================

Busca el contacto del tipo pedido **en profundidad**, descendiendo por los
hijos sin cruzar la frontera de una empresa (``is_company``), y si no lo
encuentra sube al padre y repite. El valor por defecto es el contacto, y si
tampoco hay, el propio partner. Un ``self.children.filter(type=…)`` pasa los
casos planos y falla en cuanto hay tres niveles — que es el caso para el que
existe.

Qué haría fallar a cada control
--------------------------------

``TestDisplayAddress.test_the_country_template_governs_the_order``
    El eje. Lo haría fallar formatear en Python en vez de rellenar la
    plantilla del país.

``TestDisplayAddress.test_without_country_it_falls_back_to_the_default``
    CONTROL: sin país no hay plantilla, y la fuente tiene una por defecto.

``TestAddressGet.test_it_descends_two_levels``
    CONTROL de la profundidad: con un solo nivel, un ``filter`` plano pasaría.

``TestAddressGet.test_it_does_not_cross_into_another_company``
    CONTROL de la frontera: es la mitad que un recorrido ingenuo se salta.
"""
import pytest

from addons.base.models.res_country import ResCountry, ResCountryState
from addons.base.models.res_partner import ResPartner
from tools.misc import street_split

pytestmark = pytest.mark.integration


#: Los dos países se leen del **seed**, no se fabrican ni se mutan.
#:
#: La primera versión de este archivo creaba «México» con
#: ``get_or_create(code='MX', defaults={'name': 'México'})`` y le asignaba una
#: plantilla. Las dos mitades estaban mal y el mismo caso las destapó: ``MX``
#: **ya está sembrado** (``res_country_data.py:187``), así que ``defaults`` se
#: ignoró y el nombre real es ``Mexico`` sin acento; y el ``save()`` de la
#: plantilla habría **mutado una fila del seed** en una base reusada, que es la
#: trampa que costó un rojo falso al cerrar la tarea #93.
#:
#: Leerlos en vez de fabricarlos además da el control más fuerte: Japón viene
#: sembrado con el orden **invertido** —código postal, estado, ciudad, calle—
#: y México con el suyo. Ningún formateador cableado en Python produce los dos.
@pytest.fixture
def mexico(db):
    return ResCountry.objects.get(code='MX')


@pytest.fixture
def japon(db):
    return ResCountry.objects.get(code='JP')


@pytest.fixture
def jalisco(mexico):
    """Un estado propio — el seed no trae ninguno (medido: 0 filas)."""
    state, _ = ResCountryState.objects.get_or_create(
        country=mexico, code='JAL', defaults={'name': 'Jalisco'})
    return state


@pytest.fixture
def osaka(japon):
    state, _ = ResCountryState.objects.get_or_create(
        country=japon, code='27', defaults={'name': 'Osaka'})
    return state


class TestStreetSplit:
    """≙ ``tools.street_split`` — nombre, número y número secundario."""

    def test_it_splits_name_and_number(self):
        assert street_split('Av. Vallarta 1300') == {
            'street_name': 'Av. Vallarta',
            'street_number': '1300',
            'street_number2': '',
        }

    def test_the_second_number_comes_after_a_dash(self):
        assert street_split('Av. Vallarta 1300 - 4B')['street_number2'] == '4B'

    def test_a_street_without_a_number_keeps_the_whole_name(self):
        assert street_split('Calle Sin Numero') == {
            'street_name': 'Calle Sin Numero',
            'street_number': '',
            'street_number2': '',
        }

    def test_an_empty_street_gives_three_empty_strings(self):
        assert street_split('') == {
            'street_name': '', 'street_number': '', 'street_number2': ''}

    def test_none_is_treated_as_empty(self):
        """CONTROL — la fuente hace ``street or ''`` antes de casar."""
        assert street_split(None)['street_name'] == ''


class TestDisplayAddress:
    """≙ ``_display_address`` — la plantilla la pone el país."""

    def _partner(self, **extra):
        data = dict(name='Cliente', street='Av. Vallarta 1300',
                    street2='Piso 4', zip='44100', city='Guadalajara')
        data.update(extra)
        return ResPartner.objects.create(**data)

    def test_the_country_template_governs_the_order(self, jalisco, mexico):
        who = self._partner(country=mexico, state=jalisco)
        assert who._display_address() == (
            'Av. Vallarta 1300\nPiso 4\n44100 Guadalajara, JAL\nMexico')

    def test_the_SAME_data_comes_out_inverted_in_japan(self, osaka, japon):
        """El eje, en su forma discriminante: mismos datos, otro orden.

        Japón sembrado pide código postal, estado, ciudad y luego la calle
        (``res_country_data.py:144``). Un formateador cableado en Python
        —«calle, ciudad, CP»— pasa el caso mexicano y falla aquí; ése es el
        error que no se ve hasta que hay un cliente allá.
        """
        who = self._partner(country=japon, state=osaka)
        assert who._display_address() == (
            '44100\nOsaka Guadalajara\nAv. Vallarta 1300\nPiso 4\nJapan')

    def test_without_country_it_falls_back_to_the_default(self, db):
        """CONTROL — sin país no hay plantilla; la fuente trae una."""
        who = self._partner()
        assert who._display_address() == (
            'Av. Vallarta 1300\nPiso 4\nGuadalajara  44100\n')

    def test_a_missing_field_becomes_an_empty_string(self, mexico):
        """La fuente usa ``defaultdict(str)``: nada revienta por ausencia."""
        who = self._partner(country=mexico, street2='', city='')
        assert 'None' not in who._display_address()

    def test_the_company_name_goes_on_top(self, mexico):
        parent = ResPartner.objects.create(name='Kaupamex SA',
                                           is_company=True)
        who = self._partner(country=mexico, parent=parent)
        assert who._display_address().startswith('Kaupamex SA\n')

    def test_without_company_drops_it(self, mexico):
        """CONTROL del argumento — sin él la bandera sería decorativa."""
        parent = ResPartner.objects.create(name='Kaupamex SA',
                                           is_company=True)
        who = self._partner(country=mexico, parent=parent)
        assert not who._display_address(without_company=True).startswith(
            'Kaupamex SA')

    def test_the_dependency_list_names_the_address_fields(self, db):
        depends = ResPartner._display_address_depends()
        assert 'country' in depends and 'state' in depends
        assert 'street' in depends


class TestCountryName:
    """≙ ``_get_country_name`` — cadena vacía, nunca ``None``."""

    def test_without_country_it_is_the_empty_string(self, db):
        who = ResPartner.objects.create(name='Sin país')
        assert who._get_country_name() == ''

    def test_with_country_it_is_its_name(self, mexico):
        who = ResPartner.objects.create(name='Con país', country=mexico)
        assert who._get_country_name() == 'Mexico'


class TestAllAddr:
    """≙ ``_get_all_addr`` — la forma que consume el cálculo de impuestos."""

    def test_it_returns_one_entry_with_the_country_code(self, mexico):
        who = ResPartner.objects.create(
            name='Cliente', street='Av. Vallarta 1300', zip='44100',
            city='Guadalajara', country=mexico)
        assert who._get_all_addr() == [{
            'contact_type': 'Av. Vallarta 1300',
            'street': 'Av. Vallarta 1300',
            'zip': '44100',
            'city': 'Guadalajara',
            'country': 'MX',
        }]


class TestAddressGet:
    """≙ ``address_get`` — búsqueda en profundidad, sin cruzar empresas."""

    def test_without_children_it_returns_itself(self, db):
        who = ResPartner.objects.create(name='Solo', is_company=True)
        assert who.address_get(['delivery'])['delivery'] == who.pk

    def test_it_finds_the_child_of_the_asked_type(self, db):
        company = ResPartner.objects.create(name='Empresa', is_company=True)
        delivery = ResPartner.objects.create(
            name='Bodega', parent=company, type=ResPartner.TYPE_DELIVERY)
        assert company.address_get(['delivery'])['delivery'] == delivery.pk

    def test_it_descends_two_levels(self, db):
        """CONTROL — con un nivel, un filtro plano pasaría igual."""
        company = ResPartner.objects.create(name='Empresa', is_company=True)
        middle = ResPartner.objects.create(name='Sucursal', parent=company)
        deep = ResPartner.objects.create(
            name='Bodega', parent=middle, type=ResPartner.TYPE_DELIVERY)
        assert company.address_get(['delivery'])['delivery'] == deep.pk

    def test_it_does_not_cross_into_another_company(self, db):
        """CONTROL — la frontera es ``is_company``, y es la mitad que se salta
        un recorrido ingenuo."""
        company = ResPartner.objects.create(name='Empresa', is_company=True)
        other = ResPartner.objects.create(
            name='Filial', parent=company, is_company=True)
        ResPartner.objects.create(
            name='Bodega ajena', parent=other,
            type=ResPartner.TYPE_DELIVERY)
        assert company.address_get(['delivery'])['delivery'] == company.pk

    def test_it_climbs_to_the_parent_when_it_is_a_child(self, db):
        company = ResPartner.objects.create(name='Empresa', is_company=True)
        invoice = ResPartner.objects.create(
            name='Facturación', parent=company,
            type=ResPartner.TYPE_INVOICE)
        contact = ResPartner.objects.create(name='Ana', parent=company)
        assert contact.address_get(['invoice'])['invoice'] == invoice.pk

    def test_contact_is_always_asked_for(self, db):
        """La fuente añade ``contact`` al conjunto pedido, siempre."""
        who = ResPartner.objects.create(name='Solo', is_company=True)
        assert 'contact' in who.address_get(['delivery'])
