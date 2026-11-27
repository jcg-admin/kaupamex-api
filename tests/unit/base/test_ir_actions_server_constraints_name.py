"""Restricciones y nombre calculado de ``ir.actions.server``.

≙ ``odoo19c: odoo/addons/base/models/ir_actions.py:605-606`` (``name`` y
``automated_name`` calculados y almacenados), ``:843-849``
(``_compute_name``), ``:960-965`` (``_check_python_code``) y ``:967-973``
(``_check_children``).
Diseño: ``designs/ir-actions-server-constraints-name.md``.
"""

import pytest

from addons.base.models import IrActionsServer, IrModel
from exceptions import ValidationError
from orm.environments import sudo

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


def _create(**values):
    return IrActionsServer.create({
        'model_id': IrModel._get_id('res.partner'), **values})


def test_name_and_automated_name_are_stored_computes():
    fields_ = IrActionsServer._fields
    assert (fields_['name'].compute, fields_['name'].store,
            fields_['name'].readonly) == ('_compute_name', True, False)
    assert (fields_['automated_name'].compute,
            fields_['automated_name'].store) == ('_compute_name', True)


def test_the_compute_depends_on_the_name_depends():
    depends = IrActionsServer._compute_name._depends
    assert callable(depends)


def test_the_three_methods_are_constraints():
    assert IrActionsServer._check_python_code._constrains == ('code',)
    assert IrActionsServer._check_children._constrains == (
        'parent_id', 'child_ids')


def test_a_new_action_without_name_takes_the_generated_one():
    action = _create(state='object_create',
                     crud_model_id=IrModel._get_id('res.partner'))
    assert action.automated_name == action.name != ''


def test_changing_the_state_through_write_regenerates_the_name():
    action = _create(state='object_create',
                     crud_model_id=IrModel._get_id('res.partner'))
    action.write({'state': 'object_write'})
    assert action.name == action.automated_name
    assert action.name != ''


def test_a_cycle_through_write_is_refused_with_the_source_message():
    parent = _create(name='A', state='multi')
    child = _create(name='B', state='multi', parent_id=parent.id)
    with pytest.raises(ValidationError,
                       match='Recursion found in child server actions'):
        parent.write({'parent_id': child.id})


def test_broken_code_is_refused_on_write():
    action = _create(name='C', state='code', code='x = 1\n')
    with pytest.raises(ValidationError):
        action.write({'code': 'if True\n    pass\n'})
