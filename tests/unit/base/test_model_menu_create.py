"""``wizard.ir.model.menu.create`` — dar entrada de menú a un modelo.

Ejercita el porte de
``odoo19c: odoo/addons/base/wizard/wizard_ir_model_menu_create.py``
(``odoo-tools@622ddc2a``).
"""
import pytest

from addons.base.models.ir_actions import IrActionsActWindow
from addons.base.models.ir_model import IrModel
from addons.base.models.ir_ui_menu import IrUiMenu
from addons.base.wizard.wizard_ir_model_menu_create import ModelMenuCreate

pytestmark = pytest.mark.django_db


@pytest.fixture
def parent_menu():
    return IrUiMenu.objects.create(name='Administración')


@pytest.fixture
def target_model():
    return IrModel.objects.create(name='Contacto', model='res.partner')


def test_the_window_action_lists_the_requested_model(parent_menu, target_model):
    """≙ ``menu_create`` (``odoo19c: :13-20``): la acción apunta al modelo."""
    accion, _ = ModelMenuCreate.menu_create(
        'Contactos', parent_menu, target_model, '/admin/contacts')
    assert accion.res_model == 'res.partner'


def test_the_window_action_defaults_to_list_and_form(parent_menu, target_model):
    """``:17``: ``'view_mode': 'list,form'``."""
    accion, _ = ModelMenuCreate.menu_create(
        'Contactos', parent_menu, target_model, '/admin/contacts')
    assert accion.view_mode == 'list,form'


def test_the_menu_item_hangs_from_the_parent(parent_menu, target_model):
    """``:23-25``: el ítem se cuelga de ``menu_id``."""
    _, item = ModelMenuCreate.menu_create(
        'Contactos', parent_menu, target_model, '/admin/contacts')
    assert item.parent_id == parent_menu.pk


def test_the_menu_item_carries_the_given_name(parent_menu, target_model):
    _, item = ModelMenuCreate.menu_create(
        'Contactos', parent_menu, target_model, '/admin/contacts')
    assert item.name == 'Contactos'


def test_the_menu_item_carries_the_route_the_caller_gave(parent_menu, target_model):
    """Divergencia declarada: ``ir.ui.menu`` de este árbol enlaza por ``route``
    —la ruta del SPA— y no por el campo ``action`` de la referencia."""
    _, item = ModelMenuCreate.menu_create(
        'Contactos', parent_menu, target_model, route='/admin/contacts')
    assert item.route == '/admin/contacts'


def test_both_records_land_in_the_database(parent_menu, target_model):
    """La fuente crea dos registros; aquí también — el asistente no perdió
    ninguna de sus dos mitades."""
    accion, item = ModelMenuCreate.menu_create(
        'Contactos', parent_menu, target_model, '/admin/contacts')
    assert IrActionsActWindow.objects.filter(pk=accion.pk).exists()
    assert IrUiMenu.objects.filter(pk=item.pk).exists()


def test_a_custom_view_mode_is_respected(parent_menu, target_model):
    accion, _ = ModelMenuCreate.menu_create(
        'Contactos', parent_menu, target_model, '/admin/contacts',
        view_mode='kanban,form')
    assert accion.view_mode == 'kanban,form'
