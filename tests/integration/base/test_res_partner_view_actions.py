"""Tests — las dos acciones de vista de ``res.partner``.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/res_partner.py``:
``open_commercial_entity`` (``:1023-1031``) y ``view_header_get``
(``:1204-1210``).

Las dos son de la capa de presentación y aun así son **conducta**, no XML:
una devuelve el descriptor de la ventana que hay que abrir y la otra el
título de la lista. Ninguna toca un arch, que es lo que separa a estas dos de
``_get_view`` / ``_view_get_address`` — declarados divergencia de mecanismo en
``FormatAddressMixin`` porque sí mutan nodos con XPath.

Qué haría fallar a cada control se declara en cada caso.
"""
import pytest

from addons.base.models.res_partner import ResPartner, ResPartnerCategory
from orm.environments import context_scope

pytestmark = pytest.mark.integration


class TestOpenCommercialEntity:
    """≙ ``open_commercial_entity`` (``:1023-1031``).

    Docstring de la fuente, verbatim: *"Utility method used to add an "Open
    Company" button in partner views"*.
    """

    def test_it_points_at_the_commercial_entity_of_a_child(self, db):
        """El eje: desde un contacto, la ventana abre a SU empresa.

        Qué lo haría fallar: devolver el ``id`` propio. El botón «Abrir
        empresa» abriría el contacto sobre el que se pulsó, que es no hacer
        nada.
        """
        company = ResPartner.objects.create(name='Matriz', is_company=True)
        who = ResPartner.objects.create(name='Contacto', parent=company)
        action = who.open_commercial_entity()
        assert action['res_id'] == company.pk

    def test_a_loose_partner_points_at_itself(self, db):
        """CONTROL de la otra mitad de ``commercial_partner``.

        Un partner sin padre **es** su propia entidad comercial. Sin este
        caso, una implementación que siempre subiera al padre reventaría aquí
        en vez de devolver el propio registro.
        """
        who = ResPartner.objects.create(name='Suelto')
        assert who.open_commercial_entity()['res_id'] == who.pk

    def test_the_descriptor_carries_the_four_keys_of_the_source(self, db):
        """CONTROL de la forma — es un contrato con quien lo consume.

        Qué lo haría fallar: devolver sólo el id. Quien recibe el descriptor
        necesita saber qué modelo, qué vista y dónde abrirla.
        """
        who = ResPartner.objects.create(name='Suelto')
        action = who.open_commercial_entity()
        assert action['type'] == 'ir.actions.act_window'
        assert action['res_model'] == 'res.partner'
        assert action['view_mode'] == 'form'
        assert action['target'] == 'current'


class TestViewHeaderGet:
    """≙ ``view_header_get`` (``:1204-1210``)."""

    def test_with_a_category_in_context_it_names_it(self, db):
        """El eje: el título de la lista dice por qué etiqueta está filtrada."""
        tag = ResPartnerCategory.objects.create(name='Mayorista')
        with context_scope(category_id=tag.pk):
            assert ResPartner.view_header_get(None, 'list') == 'Contactos: Mayorista'

    def test_without_a_category_there_is_no_header(self, db):
        """CONTROL de la guarda del contexto.

        Qué lo haría fallar: devolver un título siempre. La lista sin filtro
        llevaría una cabecera que promete un recorte que no existe.
        """
        assert ResPartner.view_header_get(None, 'list') is None

    def test_a_category_id_that_does_not_exist_gives_no_header(self, db):
        """CONTROL del caso que la fuente NO cubre y aquí sí revienta.

        Allá ``browse(id_inexistente).name`` devuelve ``False`` sobre un
        recordset vacío; aquí un ``get`` levantaría ``DoesNotExist``. La
        cabecera es decoración: que un id muerto en el contexto tumbe la lista
        sería peor que no ponerla.
        """
        with context_scope(category_id=9_999_999):
            assert ResPartner.view_header_get(None, 'list') is None
