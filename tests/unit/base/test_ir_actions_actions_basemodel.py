"""``ir.actions.actions`` y ``act_window_close`` sobre ``models.BaseModel``.

≙ ``odoo19c: odoo/addons/base/models/ir_actions.py:55-259``
(``ir.actions.actions``), ``:428-443`` (``act_window_close``), ``:388-397``
(``act_window._get_action_dict``) y
``odoo/addons/base/security/ir.model.access.csv:100,102``.
Diseño: ``designs/ir-actions-actions-basemodel.md``.
"""

import pytest
from django.db import connection

import models
from addons.base.models import (
    IrFilters, IrModelData, ResGroups, ResPartner, ResUsers)
from addons.base.models.ir_actions import (
    IrActionsActions, IrActionsActWindow, IrActionsActWindowClose,
    IrActionsTodo)
from addons.base.models.ir_embedded_actions import IrEmbeddedActions
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.registry import registry_of

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _as_superuser(request):
    """El ``TransactionCase`` de la fuente corre como superusuario; las
    pruebas que no miden permisos lo reproducen con ``sudo()``. La del ACL
    mide permisos y corre sin él."""
    if request.node.name.startswith('test_an_internal_user'):
        yield
        return
    with sudo():
        yield


def _actions():
    return Environment()['ir.actions.actions']


def test_actions_is_a_basemodel_with_the_source_attributes():
    assert issubclass(IrActionsActions, models.BaseModel)
    assert (IrActionsActions._name, IrActionsActions._description,
            IrActionsActions._table, IrActionsActions._order,
            IrActionsActions._allow_sudo_commands) == (
        'ir.actions.actions', 'Actions', 'ir_actions', 'name, id', False)


def test_close_is_a_basemodel_on_the_actions_table():
    assert issubclass(IrActionsActWindowClose, models.BaseModel)
    assert (IrActionsActWindowClose._name,
            IrActionsActWindowClose._description,
            IrActionsActWindowClose._table,
            IrActionsActWindowClose._inherit,
            IrActionsActWindowClose._allow_sudo_commands) == (
        'ir.actions.act_window_close', 'Action Window Close', 'ir_actions',
        ['ir.actions.actions'], False)


def test_close_defaults_its_type():
    close = Environment()['ir.actions.act_window_close'].create(
        {'name': 'Cerrar'})
    assert close.type == 'ir.actions.act_window_close'


def test_close_readable_fields_add_effect_and_infos():
    """``:437-443``."""
    readable = Environment()['ir.actions.act_window_close'] \
        ._get_readable_fields()
    assert {'effect', 'infos'} <= readable
    assert readable - {'effect', 'infos'} == _actions()._get_readable_fields()


def _copy_window_row(source_id, new_id=None):
    """Copia por SQL la fila de una acción de ventana, sin pasar por el ORM:
    la caché de ``_existing`` no se entera."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'ir_act_window' AND column_name <> 'id'")
        columns = ', '.join(f'"{row[0]}"' for row in cursor.fetchall())
        if new_id is None:
            cursor.execute(
                f"INSERT INTO ir_act_window ({columns}) SELECT {columns} "
                f"FROM ir_act_window WHERE id = %s RETURNING id",
                [source_id])
            return cursor.fetchone()[0]
        cursor.execute(
            f"INSERT INTO ir_act_window (id, {columns}) SELECT %s, "
            f"{columns} FROM ir_act_window WHERE id = %s",
            [new_id, source_id])
        return new_id


def _delete_window_row(row_id):
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM ir_act_window WHERE id = %s", [row_id])


def test_create_write_and_unlink_clear_the_registry_cache():
    """``create``, ``write`` y ``unlink`` (``:110-133``): la caché de
    ``_existing`` de la acción de ventana se limpia."""
    window = IrActionsActWindow.create(
        {'name': 'Ventana', 'res_model': 'res.partner'})
    IrActionsActWindow._existing()
    raw_id = _copy_window_row(window.id)
    assert raw_id not in IrActionsActWindow._existing()
    action = _actions().create({'name': 'Base', 'type': 'ir.actions.actions'})
    assert raw_id in IrActionsActWindow._existing()
    for change in (lambda: action.write({'name': 'Otra'}),
                   lambda: action.unlink()):
        registry_of(IrActionsActWindow).clear_cache()
        IrActionsActWindow._existing()
        _delete_window_row(raw_id)
        assert raw_id in IrActionsActWindow._existing()
        change()
        assert raw_id not in IrActionsActWindow._existing()
        _copy_window_row(window.id, raw_id)


def test_unlink_removes_its_tasks_and_its_filters():
    """``unlink`` (``:123-133``): *"ondelete cascade will not work on
    ir.actions.actions so we will need to do it manually"*. Sobre una acción
    de ventana —un subtipo— la cascada de Django tampoco llega: el
    ``Many2one`` de los filtros y de las tareas apunta a
    ``ir.actions.actions``.
    Los ``ir.filters`` archivados también se borran (``active_test=False``).
    """
    window = IrActionsActWindow.create(
        {'name': 'Ventana', 'res_model': 'res.partner'})
    task = IrActionsTodo.create({'action_id': window.id})
    archived = IrFilters.create({'name': 'Archivado',
                                 'model_id': 'res.partner',
                                 'action_id': window.id, 'active': False})
    window.unlink()
    assert not IrActionsTodo.objects.filter(pk=task.id).exists()
    assert not IrFilters.objects.filter(pk=archived.id).exists()


def test_xml_id_is_the_external_id():
    """``_compute_xml_id`` (``:105-108``)."""
    action = _actions().create({'name': 'Base', 'type': 'ir.actions.actions'})
    IrModelData.objects.create(module='base', name='action_xyz_4a',
                               model='ir.actions.actions', res_id=action.id)
    assert action.xml_id == 'base.action_xyz_4a'


def test_action_dict_reads_computed_fields():
    """``_get_action_dict`` (``:236-245``) lee con ``read()``: los campos
    calculados (``xml_id``, ``display_name``) salen en el diccionario."""
    action = _actions().create({'name': 'Base', 'type': 'ir.actions.actions'})
    result = action._get_action_dict()
    assert {'xml_id', 'display_name', 'id', 'name', 'type'} <= set(result)
    assert result['name'] == 'Base'


def test_window_action_dict_expands_embedded_actions():
    """``act_window._get_action_dict`` (``:388-397``)."""
    target = IrFilters.create({'name': 'Activo', 'model_id': 'res.partner'})
    window = IrActionsActWindow.create(
        {'name': 'Ventana', 'res_model': 'res.partner'})
    embedded = IrEmbeddedActions.create({
        'parent_action_id': window.id, 'parent_res_model': 'ir.filters',
        'python_method': 'get_filters', 'name': 'Embebida'})
    result = window.with_context(active_id=target.id)._get_action_dict()
    assert [row['id'] for row in result['embedded_action_ids']] == [
        embedded.id]
    assert set(result['embedded_action_ids'][0]) == (
        IrEmbeddedActions._get_readable_fields(embedded) | {'id'})


@pytest.mark.parametrize('model', ['ir.actions.actions',
                                   'ir.actions.act_window_close'])
def test_an_internal_user_cannot_read_them(model):
    """ACL de ``group_system`` (``ir.model.access.csv:100,102``)."""
    with sudo():
        partner = ResPartner.objects.create(name=model, email='')
        user = ResUsers.objects.create(login=f'{model}@kaupamex.test',
                                       partner=partner)
        user.group_ids.set([ResGroups.objects.get(
            pk=IrModelData._xmlid_to_res_id('base.group_user',
                                            raise_if_not_found=True))])
    with user_scope(user.pk):
        with pytest.raises(AccessError):
            Environment(uid=user.pk)[model].browse().check_access('read')
