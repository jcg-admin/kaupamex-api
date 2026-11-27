"""``ir.embedded.actions`` sobre ``models.BaseModel``.

≙ ``odoo19c: odoo/addons/base/models/ir_embedded_actions.py:8-111``,
``odoo/addons/base/models/ir_actions.py:332,336-339`` (``embedded_action_ids``
calculado de la acción de ventana), ``ir_filters.py:23``,
``security/ir.model.access.csv:109`` y ``security/base_security.xml:208-227``.
Diseño: ``designs/ir-embedded-actions-basemodel.md``.
"""

import pytest
from django.db import IntegrityError, connection, transaction

import models
from addons.base.models import (
    IrModelData, IrRule, ResGroups, ResPartner, ResUsers)
from addons.base.models.ir_actions import IrActionsActions, IrActionsActWindow
from addons.base.models.ir_embedded_actions import IrEmbeddedActions
from addons.base.models.ir_filters import IrFilters
from exceptions import UserError
from orm.environments import Environment, sudo, user_scope

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _as_superuser():
    """El ``TransactionCase`` de la fuente corre como superusuario; las
    pruebas que no miden permisos lo reproducen con ``sudo()``."""
    with sudo():
        yield


def _window(name='Socios'):
    return IrActionsActWindow.create(
        {'name': name, 'res_model': 'res.partner'})


def _embedded(parent, **values):
    vals = {'parent_action_id': parent.id, 'parent_res_model': 'res.partner',
            'python_method': 'action_view_partner_xyz', 'name': 'Embebida'}
    vals.update(values)
    return IrEmbeddedActions.create(vals)


def test_it_is_a_basemodel_with_the_source_attributes():
    assert issubclass(IrEmbeddedActions, models.BaseModel)
    assert (IrEmbeddedActions._name, IrEmbeddedActions._description,
            IrEmbeddedActions._order) == (
        'ir.embedded.actions', 'Embedded Actions', 'sequence, id')


def test_the_fields_carry_the_source_names():
    names = {field.name for field in IrEmbeddedActions._meta.get_fields()}
    assert {'parent_action_id', 'action_id', 'user_id', 'groups_ids',
            'filter_ids'} <= names
    assert not {'parent_action', 'action', 'user', 'groups', 'system'} & names
    assert IrEmbeddedActions._meta.get_field('context').get_internal_type() \
        == 'CharField'


def test_groups_ids_uses_the_table_the_source_derives():
    """``fields_relational.py:1291-1295``: tablas ordenadas + ``_rel``."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'ir_embedded_actions_res_groups_rel'")
        columns = {row[0] for row in cursor.fetchall()}
    assert {'ir_embedded_actions_id', 'res_groups_id'} <= columns


def test_the_filter_field_is_embedded_action_id():
    field = IrFilters._meta.get_field('embedded_action_id')
    assert (field.name, field.column, field.related_model) == (
        'embedded_action_id', 'embedded_action_id', IrEmbeddedActions)


def test_create_names_it_after_its_action_and_drops_the_extra_field():
    """``create`` (``:43-55``)."""
    action = IrActionsActions.objects.create(
        name='Acción base', type='ir.actions.act_window')
    record = IrEmbeddedActions.create({
        'parent_action_id': _window().id, 'parent_res_model': 'res.partner',
        'action_id': action.pk, 'python_method': False})
    assert record.name == 'Acción base'
    assert not record.python_method
    by_method = _embedded(_window(), action_id=action.pk)
    assert not by_method.action_id
    assert by_method.python_method == 'action_view_partner_xyz'


def test_python_method_is_null_so_the_source_constraint_holds():
    """``_check_only_one_action_defined`` (``:31-37``) mide ``IS NULL``."""
    parent = _window()
    with pytest.raises(IntegrityError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO ir_embedded_actions (parent_action_id, "
                "parent_res_model, name, create_date, write_date) "
                "VALUES (%s, 'res.partner', '{\"en_US\": \"x\"}', "
                "now(), now())", [parent.id])


#: El modelo padre de las pruebas de visibilidad: ``ir.filters`` está sobre
#: ``models.BaseModel`` en este árbol y declara ``get_filters``.
PARENT = 'ir.filters'
METHOD = 'get_filters'


def _filter(name):
    return IrFilters.create({'name': name, 'model_id': 'res.partner'})


def test_is_visible_follows_active_id_record_and_domain():
    """``_compute_is_visible`` (``:75-96``)."""
    shown = _filter('Visible')
    other = _filter('Otro')
    record = _embedded(_window(), parent_res_model=PARENT,
                       python_method=METHOD,
                       domain=repr([('name', '=', 'Visible')]))
    assert record.with_context(active_id=shown.id).is_visible
    record.invalidate_recordset(['is_visible'])
    assert not record.with_context(active_id=other.id).is_visible


def test_is_visible_is_false_without_active_id():
    record = _embedded(_window(), parent_res_model=PARENT,
                       python_method=METHOD)
    assert not record.is_visible


def test_a_missing_python_method_hides_it():
    shown = _filter('Visible')
    record = _embedded(_window(), parent_res_model=PARENT,
                       python_method='no_such_method_xyz')
    assert not record.with_context(active_id=shown.id).is_visible


def test_window_embedded_action_ids_lists_only_the_visible_ones():
    """``_compute_embedded_actions`` (``ir_actions.py:336-339``)."""
    active = _filter('Visible')
    parent = _window()
    shown = _embedded(parent, parent_res_model=PARENT, python_method=METHOD)
    _embedded(parent, parent_res_model=PARENT,
              python_method='no_such_method_xyz', name='Oculta')
    window = parent.with_context(active_id=active.id)
    assert list(window.embedded_action_ids.ids) == [shown.id]


def test_a_record_with_a_module_xmlid_cannot_be_deleted():
    """``_compute_is_deletable`` (``:66-73``) y
    ``_unlink_if_action_deletable`` (``:98-103``)."""
    custom = _embedded(_window())
    assert custom.is_deletable
    shipped = _embedded(_window(), name='De módulo')
    IrModelData.objects.create(
        module='base', name='embedded_xyz_shipped',
        model='ir.embedded.actions', res_id=shipped.id)
    shipped.invalidate_recordset()
    assert not shipped.is_deletable
    with pytest.raises(UserError):
        shipped.unlink()
    custom.unlink()
    assert not IrEmbeddedActions.objects.filter(pk=custom.id).exists()


def test_readable_fields_are_the_source_set():
    assert Environment()['ir.embedded.actions']._get_readable_fields() == {
        'name', 'parent_action_id', 'parent_res_id', 'parent_res_model',
        'action_id', 'python_method', 'user_id', 'is_deletable',
        'default_view_mode', 'filter_ids', 'domain', 'context', 'groups_ids'}


def test_access_row_and_record_rules_are_seeded():
    """``ir.model.access.csv:109`` y ``base_security.xml:208-227``."""
    names = set(IrRule.objects.filter(
        model_name='ir.embedded.actions').values_list('name', flat=True))
    assert names == {
        'Users can modify or delete embedded actions that they have created '
        'or that are shared',
        'Admins have all the rights on embedded actions'}
    partner = ResPartner.objects.create(name='internal-3d', email='')
    user = ResUsers.objects.create(login='internal-3d@kaupamex.test',
                                   partner=partner)
    user.group_ids.set([ResGroups.objects.get(pk=IrModelData._xmlid_to_res_id(
        'base.group_user', raise_if_not_found=True))])
    with user_scope(user.pk):
        assert Environment(uid=user.pk)['ir.embedded.actions'].browse() \
            .check_access('read') is None
