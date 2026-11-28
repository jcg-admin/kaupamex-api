"""``action_id`` y ``action_launch`` de ``ir.actions.todo``.

≙ ``odoo19c: odoo/addons/base/models/ir_actions.py:1347-1422``; los dos
registros de ``unlink`` se siembran en
``odoo19c: odoo/addons/base/views/base_menus.xml:37-47``.
Diseño: ``designs/ir-actions-todo-action-id-launch.md``.
"""

import pytest

from addons.base.models import IrActionsTodo, IrModelData
from addons.base.models.ir_actions import (
    IrActionsActWindow,
    IrActionsClient,
)
from orm.environments import sudo

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


def _window(**values):
    return IrActionsActWindow.create({
        'name': 'Asistente', 'res_model': 'res.partner',
        'view_mode': 'form', **values})


def test_the_field_keeps_the_source_name():
    field = IrActionsTodo._meta.get_field('action_id')
    assert (field.column, field.null) == ('action_id', False)
    assert IrActionsTodo._rec_name == 'action_id'


def test_launching_marks_the_step_done():
    step = IrActionsTodo.create({'action_id': _window().id})
    step.action_launch()
    assert step.state == 'done'


def test_a_window_action_gets_its_evaluated_context():
    window = _window(context="{'res_id': 7, 'default_name': 'x'}")
    result = IrActionsTodo.create({'action_id': window.id}).action_launch()
    assert result['id'] == window.id
    assert result['res_id'] == 7
    assert result['context'] == {'default_name': 'x', 'disable_log': True}


def test_a_client_action_is_returned_as_read():
    client = IrActionsClient.create({'name': 'Recargar', 'tag': 'reload'})
    result = IrActionsTodo.create({'action_id': client.id}).action_launch()
    assert result['tag'] == 'reload'
    assert 'disable_log' not in str(result.get('context', ''))


def test_unlink_keeps_the_open_menu_step_with_the_menu_action():
    menu_action = IrActionsClient.create({
        'name': 'Open Settings Menu', 'tag': 'reload'})
    step = IrActionsTodo.create({
        'name': 'Open Menu', 'action_id': _window().id, 'state': 'done'})
    for name, model, record in (
            ('action_client_base_menu', 'ir.actions.client', menu_action),
            ('open_menu', 'ir.actions.todo', step)):
        IrModelData.create({'module': 'base', 'name': name,
                            'model': model, 'res_id': record.id})
    step.unlink()
    assert step.exists()
    assert step.action_id.id == menu_action.id
