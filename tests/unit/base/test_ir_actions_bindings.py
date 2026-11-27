"""``binding_model_id``, ``get_bindings`` y ``_get_bindings``.

≙ ``odoo19c: odoo/addons/base/models/ir_actions.py:74-75,155-223,989-1000``
y ``odoo/addons/base/models/ir_actions_report.py:244-254``.
Diseño: ``designs/ir-actions-bindings.md``.
"""

import pytest

from addons.base.models import IrModelData, ResGroups, ResPartner, ResUsers
from addons.base.models.ir_actions import (
    IrActionsActions, IrActionsActWindow, IrActionsServer)
from addons.base.models.ir_model import IrModel
from orm.environments import Environment, sudo, user_scope

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _as_superuser(request):
    """El ``TransactionCase`` de la fuente corre como superusuario; la prueba
    del usuario sin grupo mide permisos y corre sin él."""
    if request.node.name.startswith('test_a_user_outside'):
        yield
        return
    with sudo():
        yield


def _partner_model():
    return IrModel._get('res.partner')


def _bound_window(name, **values):
    return IrActionsActWindow.create({
        'name': name, 'res_model': 'res.partner',
        'binding_model_id': _partner_model().pk, **values})


def test_binding_model_id_replaces_the_char_column():
    field = IrActionsActWindow._meta.get_field('binding_model_id')
    assert (field.column, field.related_model) == (
        'binding_model_id', IrModel)
    names = {f.name for f in IrActionsActions._meta.get_fields()}
    assert 'binding_model_name' not in names


def test_get_bindings_lists_the_actions_bound_to_the_model():
    """``get_bindings`` (``:155-182``): ``group_ids`` y ``res_model`` salen
    del diccionario; ``name`` y ``binding_view_types`` quedan."""
    window = _bound_window('Ligada')
    bindings = Environment()['ir.actions.actions'].get_bindings(
        'res.partner')
    entry = next(row for row in bindings['action'] if row['id'] == window.id)
    assert entry['name'] == 'Ligada'
    assert entry['binding_view_types'] == 'list,form'
    assert 'res_model' not in entry and 'group_ids' not in entry


def test_bound_actions_are_sorted_by_sequence():
    """``_get_bindings`` (``:218-221``)."""
    model = _partner_model()
    later = IrActionsServer.create({
        'name': 'Después', 'model_name': 'res.partner', 'sequence': 20,
        'binding_model_id': model.pk})
    first = IrActionsServer.create({
        'name': 'Antes', 'model_name': 'res.partner', 'sequence': 5,
        'binding_model_id': model.pk})
    ids = [row['id'] for row in Environment()['ir.actions.actions']
           ._get_bindings('res.partner')['action']]
    assert ids.index(first.id) < ids.index(later.id)


def test_a_user_outside_the_action_groups_does_not_get_it():
    """``get_bindings`` (``:166-169``)."""
    with sudo():
        system = ResGroups.objects.get(pk=IrModelData._xmlid_to_res_id(
            'base.group_system', raise_if_not_found=True))
        window = _bound_window('Sólo sistema')
        window.write({'group_ids': [(6, 0, [system.pk])]})
        partner = ResPartner.objects.create(name='bind-user', email='')
        user = ResUsers.objects.create(login='bind-user@kaupamex.test',
                                       partner=partner)
        user.group_ids.set([ResGroups.objects.get(
            pk=IrModelData._xmlid_to_res_id('base.group_user',
                                            raise_if_not_found=True))])
    with user_scope(user.pk):
        bindings = Environment(uid=user.pk)['ir.actions.actions'] \
            .get_bindings('res.partner')
    assert window.id not in [row['id'] for row in bindings.get('action', [])]


def test_server_create_and_unlink_action_set_the_binding():
    """``create_action`` y ``unlink_action`` (``:989-1000``)."""
    model = _partner_model()
    action = IrActionsServer.create({'name': 'Contextual',
                                     'model_name': 'res.partner'})
    action.create_action()
    assert action.binding_model_id.pk == model.pk
    assert action.binding_type == 'action'
    action.unlink_action()
    assert not action.binding_model_id
