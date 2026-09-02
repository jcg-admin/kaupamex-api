"""#311 — el inverso declarado se INVOCA al escribir el campo.

#305 declaro ``inverse=`` en los dos campos que la referencia declara
inversibles, y los dos metodos ya existian en el arbol desde el porte de crm.
Lo que faltaba era el ejecutor: nada llamaba a un inverso declarado.

Veredicto por el criterio de las dos categorias: **el stack tiene con que
construirlo**. No hay simbolo hecho —Django no conoce la nocion de un metodo
inverso sobre un campo— pero las primitivas estan: ``determine()`` ya vive en
``orm/fields.py:1039`` y su hermano ``determine_domain`` ya se porto; el punto
de escritura es ``write()``, que este arbol ya declara. Ninguna dependencia de
fuera del INVENTORY.

Medido con cada guarda anulada
==============================

Son dos y cada una tiene su control, porque anular una no mueve a la otra.

**1. La llamada desde ``write``** (``orm/models.py:1881``). Sustituyendo el
cuerpo del bucle por ``pass``, el modulo pasa de **8 passed** a **4 failed,
4 passed**. Caen los cuatro que escriben por ``write``. Sobreviven, y es
correcto que sobrevivan:

- ``test_the_field_declares_it`` — mide que el simbolo existe, no que se llame;
- ``test_it_dispatches_through_determine`` — llama al despachador directo, que
  es como lo llama la fuente desde su propio descriptor;
- ``test_the_column_of_the_lead_keeps_the_value_too`` — mide la columna;
- ``test_a_field_without_inverse_reaches_nothing`` — afirma una ausencia, y un
  enganche retirado la produce igual. **Ese caso no discrimina aqui** — mide el
  otro lado, que escribir un campo sin inverso no propague.

**2. El cuerpo del despachador** (``orm/fields.py:2273``). Sustituyendolo por
``return None``, el modulo pasa de **8 passed** a **5 failed, 3 passed**: cae
uno mas, ``test_it_dispatches_through_determine``, que es justo el que mide el
despacho y no el enganche.

*Metrica:* casos de este modulo que caen al anular cada una de las dos guardas.
*Ciega a:* un campo cuyo inverso se declare como invocable en vez de como
cadena — ``determine`` lo admite y ningun caso de aqui lo ejerce; y a la
transaccionalidad entre la escritura y su inverso, que es la tarea #255.
"""
import pytest
from django.apps import apps

from orm.utils import model_field_registry


CrmLead = apps.get_model('crm', 'CrmLead')
CrmTeam = apps.get_model('sales_team', 'CrmTeam')
ResCompany = apps.get_model('base', 'ResCompany')
ResPartner = apps.get_model('base', 'ResPartner')


def field_of(model, name):
    return model._meta.get_field(name)


@pytest.fixture
def partner(db):
    """El cliente llega SIN correo ni telefono, y eso es lo que se mide.

    Es la forma que la fuente da al inverso: propagar al cliente el dato que
    el usuario acaba de teclear en la iniciativa. Y ademas es la unica que hoy
    deja ver el inverso, porque ``CrmLead.save`` llama a mano a todos sus
    computos antes de escribir (``crm_lead.py:1300``): con un cliente que ya
    trae correo, ``_compute_email_from`` lo pisa antes de que la fila llegue a
    la base. Retirar esas llamadas a mano —que el motor de #273 ya hace
    innecesarias— es la tarea **#312**; este modulo no la adelanta.
    """
    return ResPartner.objects.create(
        name='Contacto Inverso', email='', phone='')


@pytest.fixture
def lead(partner):
    """La iniciativa se construye con empresa Y equipo, y no es decoracion.

    ``_compute_company_id`` (``crm_lead.py:624``) cae a ``partner_id.company_id``
    cuando no hay equipo ni responsable, y ``ResPartner`` **no declara ese
    campo** en este arbol — es el bloqueo medido de la tarea #110. Con un equipo
    cuya empresa coincide, la propuesta sobrevive las cuatro guardas y el computo
    devuelve antes de leer al cliente. Es la misma forma que
    ``tests/unit/orm/test_check_company.py:147``.
    """
    company = ResCompany.objects.create(code='inv-311', name='Inversa 311')
    team = CrmTeam.objects.create(name='Equipo inverso', company_id=company)
    return CrmLead.objects.create(
        name='Oportunidad inversa', partner_id=partner,
        company_id=company, team_id=team)


class TestTheDispatcherExists:
    """``determine_inverse`` es el hermano de ``determine_domain``, ya portado."""

    def test_the_field_declares_it(self):
        assert callable(field_of(CrmLead, 'email_from').determine_inverse)

    def test_it_dispatches_through_determine(self, lead):
        """No reimplementa el despacho: usa ``determine()``, que es quien
        resuelve el nombre de metodo contra el registro
        (``odoo19c: odoo/orm/fields.py:1922-1924``, cuyo cuerpo entero es
        ``determine(self.inverse, records)``)."""
        visto = {}
        lead.email_from = 'nuevo@ejemplo.mx'
        original = CrmLead._inverse_email_from

        def espia(self):
            visto['llamado'] = True
            return original(self)

        CrmLead._inverse_email_from = espia
        try:
            field_of(CrmLead, 'email_from').determine_inverse(lead)
        finally:
            CrmLead._inverse_email_from = original
        assert visto == {'llamado': True}


class TestWriteInvokesIt:
    """El punto de enganche es ``write``, como en la fuente."""

    def test_writing_the_field_reaches_the_partner(self, lead, partner):
        """El inverso escribe en el partner: es el efecto observable, y el
        unico que distingue «se invoco» de «se guardo la columna»."""
        lead.write({'email_from': 'nuevo@ejemplo.mx'})
        partner.refresh_from_db()
        assert partner.email == 'nuevo@ejemplo.mx'

    def test_the_column_of_the_lead_keeps_the_value_too(self, lead):
        """``store=True`` sigue vigente: el inverso NO sustituye a la columna.
        La fuente hace las dos cosas — escribe y ademas invierte."""
        lead.write({'email_from': 'ambos@ejemplo.mx'})
        lead.refresh_from_db()
        assert lead.email_from == 'ambos@ejemplo.mx'

    def test_emptying_the_field_does_not_empty_the_partner(self, lead, partner):
        """Segundo control, y discrimina el despachador de una escritura ciega.

        El inverso consulta ``_get_partner_email_update(force_void=False)``, que
        **rehusa** cuando la iniciativa se queda sin correo — para no propagar un
        vacio sobre un valor bueno (``crm_lead.py:1148-1150``). Un despachador
        que escribiera por su cuenta, sin llamar al metodo declarado, dejaria al
        cliente sin correo aqui.
        """
        lead.write({'email_from': 'bueno@ejemplo.mx'})
        partner.refresh_from_db()
        assert partner.email == 'bueno@ejemplo.mx'

        lead.write({'email_from': ''})
        partner.refresh_from_db()
        assert partner.email == 'bueno@ejemplo.mx'

    def test_the_second_declared_inverse_also_runs(self, lead, partner):
        lead.write({'phone': '555-9999'})
        partner.refresh_from_db()
        assert partner.phone == '555-9999'

    def test_a_field_without_inverse_reaches_nothing(self, lead, partner):
        """El control que discrimina: la MISMA maquinaria sobre un campo sin
        ``inverse`` no toca al partner. Sin este caso, los de arriba no
        distinguen «se invoco el inverso» de «escribir cualquier cosa propaga»."""
        antes = (partner.email, partner.phone)
        lead.write({'name': 'Otro nombre'})
        partner.refresh_from_db()
        assert (partner.email, partner.phone) == antes


class TestTheGroupingIsByMethod:
    """La fuente agrupa por metodo inverso y lo llama UNA vez por grupo
    (``odoo19c: odoo/orm/models.py:4399, 4416, 4493``)."""

    def test_two_fields_sharing_one_inverse_call_it_once(self, lead):
        veces = []
        original = CrmLead._inverse_email_from

        def counter(self):
            veces.append(1)
            return original(self)

        campos = model_field_registry(CrmLead)
        phone = campos['phone']
        inverso_previo = phone.inverse
        phone.inverse = '_inverse_email_from'
        CrmLead._inverse_email_from = counter
        try:
            lead.write({'email_from': 'uno@ejemplo.mx', 'phone': '555-1111'})
        finally:
            CrmLead._inverse_email_from = original
            phone.inverse = inverso_previo
        assert veces == [1]
