"""Tests — las restricciones y los onchange de ``res.partner``.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/res_partner.py``:
``_check_parent_id`` (``:546-549``), ``onchange_parent_id`` (``:571-583``),
``_onchange_country_id`` (``:586-589``) y ``_onchange_state`` (``:591-594``).

Son dos mecanismos distintos y conviene no confundirlos:

- **la restricción** corre al guardar y **rechaza** un estado imposible. Sin
  ella, una jerarquía cíclica se persiste y cualquier recorrido del árbol
  —``complete_name``, ``parent_path``, ``_children_sync``— no termina.
- **el onchange** corre mientras el formulario está abierto y **propone** un
  valor coherente antes de guardar. Sin él, el usuario guarda un estado de
  un país y un país distinto, que la restricción no rechaza porque no es
  imposible: sólo es falso.

Qué haría fallar a cada control se declara en cada caso.
"""
import pytest

from addons.base.models.res_country import ResCountry, ResCountryState
from addons.base.models.res_partner import ResPartner
from exceptions import ValidationError

pytestmark = pytest.mark.integration


@pytest.fixture
def mx(db):
    return ResCountry.objects.get_or_create(code='MX', defaults={'name': 'Mexico'})[0]


@pytest.fixture
def jp(db):
    return ResCountry.objects.get_or_create(code='JP', defaults={'name': 'Japon'})[0]


@pytest.fixture
def jalisco(mx):
    return ResCountryState.objects.get_or_create(
        country=mx, code='JAL', defaults={'name': 'Jalisco'})[0]


@pytest.fixture
def osaka(jp):
    return ResCountryState.objects.get_or_create(
        country=jp, code='OSK', defaults={'name': 'Osaka'})[0]


class TestRecursiveHierarchy:
    """≙ ``_check_parent_id`` (``:546-549``).

    Mensaje de la fuente, verbatim: *"You cannot create recursive Partner
    hierarchies."*
    """

    def test_a_partner_cannot_be_its_own_parent(self, db):
        """El eje. Qué lo haría fallar: retirar la guarda del ``save``."""
        who = ResPartner.objects.create(name='Ciclo de uno')
        who.parent = who
        with pytest.raises(ValidationError):
            who.save()

    def test_a_cycle_of_three_is_refused(self, db):
        """CONTROL de la profundidad del recorrido.

        Qué lo haría fallar: comprobar sólo el padre inmediato en vez de
        recorrer la cadena. A → B → C y luego A como padre de C cierra el
        ciclo sin que ningún registro sea su propio padre.
        """
        a = ResPartner.objects.create(name='A')
        b = ResPartner.objects.create(name='B', parent=a)
        c = ResPartner.objects.create(name='C', parent=b)
        a.parent = c
        with pytest.raises(ValidationError):
            a.save()

    def test_a_legitimate_chain_is_accepted(self, db):
        """CONTROL de la dirección contraria — la profundidad no es un ciclo.

        Qué lo haría fallar: un recorrido que confunda «tiene ancestros» con
        «se muerde la cola». Sin este caso, una guarda que rechazara toda
        jerarquía pasaría los dos anteriores.
        """
        a = ResPartner.objects.create(name='Raiz')
        b = ResPartner.objects.create(name='Media', parent=a)
        c = ResPartner.objects.create(name='Hoja', parent=b)
        assert c.parent.parent.pk == a.pk


class TestOnchangeCountry:
    """≙ ``_onchange_country_id`` (``:586-589``)."""

    def test_setting_a_country_clears_a_state_from_another_country(self, mx, osaka):
        """El eje: el estado de otro país deja de ser coherente."""
        who = ResPartner(name='Mudanza', state=osaka)
        who.country = mx
        who._onchange_country_id()
        assert who.state is None

    def test_the_state_of_the_same_country_survives(self, mx, jalisco):
        """CONTROL — qué lo haría fallar: limpiar el estado sin comparar.

        Sin este caso, un método que hiciera ``self.state = None`` a secas
        pasaría el anterior.
        """
        who = ResPartner(name='Coherente', state=jalisco)
        who.country = mx
        who._onchange_country_id()
        assert who.state is not None
        assert who.state.pk == jalisco.pk

    def test_without_a_country_nothing_is_cleared(self, osaka):
        """CONTROL de la guarda ``if self.country_id`` de la fuente.

        Quitar el país no puede arrastrar al estado: el usuario que borra el
        país para reescribirlo perdería el estado que ya había puesto.
        """
        who = ResPartner(name='Sin pais', state=osaka)
        who._onchange_country_id()
        assert who.state is not None


class TestOnchangeState:
    """≙ ``_onchange_state`` (``:591-594``)."""

    def test_setting_a_state_brings_its_country(self, jalisco, mx):
        """El eje: el estado manda sobre el país, no al revés."""
        who = ResPartner(name='Desde el estado')
        who.state = jalisco
        who._onchange_state()
        assert who.country is not None
        assert who.country.pk == mx.pk

    def test_a_state_of_the_same_country_does_not_change_it(self, mx, jalisco):
        """CONTROL — qué lo haría fallar: asignar el país sin comparar.

        No cambia el resultado observable, pero sí la escritura: un método
        que asignara siempre marcaría el campo como modificado y dispararía
        la sincronización del bloque de dirección sin motivo.
        """
        who = ResPartner(name='Ya coherente', country=mx, state=jalisco)
        who._onchange_state()
        assert who.country.pk == mx.pk

    def test_without_a_state_the_country_survives(self, mx):
        """CONTROL de la guarda ``if self.state_id.country_id``.

        En la fuente un Many2one vacío es un recordset vacío y ``.country_id``
        sobre él es falso. Aquí ``self.state`` es ``None`` y el mismo acceso
        levantaría ``AttributeError``: la traducción literal rompe, y este
        caso es lo que lo delata.
        """
        who = ResPartner(name='Sin estado', country=mx)
        who._onchange_state()
        assert who.country.pk == mx.pk


class TestOnchangeParent:
    """≙ ``onchange_parent_id`` (``:571-583``).

    Devuelve un diccionario, no muta: su comentario en la fuente lo dice
    —*"return values in result, as this method is used by _fields_sync()"*—.
    """

    def test_a_contact_receives_the_address_of_its_parent(self, db, mx):
        """El eje. Qué lo haría fallar: no consultar ``_get_address_values``."""
        company = ResPartner.objects.create(
            name='Matriz', is_company=True, street='Reforma 1',
            city='CDMX', country=mx)
        who = ResPartner.objects.create(name='Contacto', type=ResPartner.TYPE_CONTACT)
        who.parent = company
        result = who.onchange_parent_id()
        assert result['value']['street'] == 'Reforma 1'
        assert result['value']['city'] == 'CDMX'

    def test_without_a_parent_it_returns_nothing(self, db):
        """CONTROL de la guarda ``if not self.parent_id: return``."""
        who = ResPartner.objects.create(name='Suelto')
        assert who.onchange_parent_id() is None

    def test_a_parent_without_an_address_returns_no_value(self, db):
        """CONTROL — ``{}`` no es lo mismo que un diccionario de vacíos.

        Qué lo haría fallar: devolver ``{'value': {}}``. Propagado por
        ``_fields_sync``, un diccionario de cadenas vacías **borraría** la
        dirección del hijo en vez de dejarla como está.
        """
        company = ResPartner.objects.create(name='Matriz sin direccion', is_company=True)
        who = ResPartner.objects.create(name='Contacto', type=ResPartner.TYPE_CONTACT)
        who.parent = company
        result = who.onchange_parent_id()
        assert 'value' not in result

    def test_the_stored_type_decides_not_the_one_in_memory(self, db, mx):
        """CONTROL del ``self._origin`` de la fuente.

        ``(partner.type or self.type)`` lee **primero** el tipo guardado. Un
        registro que está en la base como ``invoice`` y al que el formulario
        acaba de cambiar el tipo a ``contact`` **no** toma la dirección del
        padre: sigue siendo una dirección de facturación propia hasta que se
        guarde.

        Qué lo haría fallar: usar ``self.type`` a secas, que es la traducción
        cómoda y la que ignora ``_origin``.
        """
        company = ResPartner.objects.create(
            name='Matriz', is_company=True, street='Reforma 1', country=mx)
        who = ResPartner.objects.create(
            name='Facturacion', type=ResPartner.TYPE_INVOICE)
        who.parent = company
        who.type = ResPartner.TYPE_CONTACT
        result = who.onchange_parent_id()
        assert 'value' not in result

    def test_a_new_record_falls_back_to_the_type_in_memory(self, db, mx):
        """CONTROL de la otra mitad de ``partner.type or self.type``.

        Sin PK no hay tipo guardado, así que decide el del formulario. Qué lo
        haría fallar: leer sólo el guardado y devolver siempre nada para un
        registro nuevo, que es el caso más común del alta.
        """
        company = ResPartner.objects.create(
            name='Matriz', is_company=True, street='Reforma 1', country=mx)
        who = ResPartner(name='Nuevo', type=ResPartner.TYPE_CONTACT, parent=company)
        result = who.onchange_parent_id()
        assert result['value']['street'] == 'Reforma 1'
