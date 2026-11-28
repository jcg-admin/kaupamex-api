"""``ir.actions.todo`` sobre ``models.BaseModel``, con su conducta.

≙ ``odoo19c: odoo/addons/base/models/ir_actions.py:1347-1422`` y
``odoo/addons/base/security/ir.model.access.csv:104``. Diseño:
``designs/basemodel-adoption-ir-actions-todo.md``.
"""

import pytest

from addons.base.models.ir_actions import IrActionsActions, IrActionsTodo
from addons.base.models.res_users import ResUsers
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _env():
    return Environment(su=True)['ir.actions.todo']


def _action(name):
    return IrActionsActions.objects.create(
        name=name, type='ir.actions.actions')


def test_only_the_lowest_sequence_stays_open():
    """``ensure_one_open_todo`` (``:1376-1380``)."""
    first = _env().create({'action_id': _action('todo-a').pk, 'sequence': 5})
    second = _env().create({'action_id': _action('todo-b').pk, 'sequence': 1})
    first.invalidate_recordset()
    second.invalidate_recordset()
    assert second.state == 'open'
    assert first.state == 'done'


def test_reopening_closes_the_other_open_step():
    """``write`` con ``state='open'`` (``:1370-1374``)."""
    first = _env().create({'action_id': _action('todo-c').pk, 'sequence': 1})
    second = _env().create({'action_id': _action('todo-d').pk, 'sequence': 2})
    assert second.state == 'done'
    second.write({'sequence': 0})
    second.action_open()
    first.invalidate_recordset()
    second.invalidate_recordset()
    assert second.state == 'open'
    assert first.state == 'done'


def test_an_internal_user_cannot_create_steps():
    """ACL de ``group_system`` (``ir.model.access.csv:104``)."""
    with sudo():
        user = ResUsers.objects.create_user(
            login='todo-internal@kaupamex.test', password='x')
    action = _action('todo-acl')
    with user_scope(user.pk), pytest.raises(AccessError):
        Environment(uid=user.pk)['ir.actions.todo'].create(
            {'action_id': action.pk})
    assert not IrActionsTodo.objects.filter(action_id=action).exists()
