"""``ir.actions.server`` e ``ir.actions.report`` sobre ``models.BaseModel``.

≙ ``odoo19c: odoo/addons/base/models/ir_actions.py:567-592`` (atributos),
``:711-734`` (``create`` y ``write``),
``odoo/addons/base/models/ir_actions_report.py:157-163`` y
``odoo/addons/base/security/ir.model.access.csv:103,107``. Diseño:
``designs/ir-actions-server-and-report-basemodel.md``.
"""

import pytest

import models

from addons.base.models import IrModelData, ResGroups, ResPartner, ResUsers
from addons.base.models.ir_actions import (
    IrActionsServer, IrActionsServerHistory)
from addons.base.models.ir_actions_report import IrActionsReport
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _group(xmlid):
    return ResGroups.objects.get(
        pk=IrModelData._xmlid_to_res_id(xmlid, raise_if_not_found=True))


def _user(login, xmlid):
    with sudo():
        partner = ResPartner.objects.create(name=login, email='')
        user = ResUsers.objects.create(login=login, partner=partner)
        user.group_ids.set([_group(xmlid)])
    return user


def _system_env(model):
    user = _user(f'{model}-system@kaupamex.test', 'base.group_system')
    return user, Environment(uid=user.pk)[model]


def test_server_actions_and_reports_are_basemodel_records():
    assert issubclass(IrActionsServer, models.BaseModel)
    assert issubclass(IrActionsReport, models.BaseModel)


def test_a_system_user_creates_and_writes_server_actions():
    """ACL de ``group_system`` (``ir.model.access.csv:107``)."""
    user, env = _system_env('ir.actions.server')
    with user_scope(user.pk):
        action = env.create({'name': 'Probe', 'model_name': 'res.partner',
                             'state': 'code'})
        action.write({'name': 'Probe 2'})
    assert IrActionsServer.objects.get(pk=action.id).name == 'Probe 2'


def test_an_internal_user_cannot_read_server_actions():
    action = IrActionsServer.objects.create(
        name='Hidden', model_name='res.partner', state='code')
    user = _user('server-internal@kaupamex.test', 'base.group_user')
    with user_scope(user.pk):
        env = Environment(uid=user.pk)['ir.actions.server']
        with pytest.raises(AccessError):
            env.browse(action.pk).check_access('read')


def test_an_internal_user_reads_reports_but_cannot_write_them():
    """``group_system`` todo (``base: ir.model.access.csv:103``) y
    ``group_user`` sólo lectura, que añade ``mail``
    (``odoo19c: addons/mail/security/ir.model.access.csv:62``)."""
    user = _user('report-internal@kaupamex.test', 'base.group_user')
    with user_scope(user.pk):
        env = Environment(uid=user.pk)['ir.actions.report']
        env.browse().check_access('read')
        with pytest.raises(AccessError):
            env.browse().check_access('write')


def test_a_portal_user_cannot_read_reports():
    user = _user('report-portal@kaupamex.test', 'base.group_portal')
    with user_scope(user.pk):
        env = Environment(uid=user.pk)['ir.actions.report']
        with pytest.raises(AccessError):
            env.browse().check_access('read')


def test_creating_a_child_copies_the_model_and_groups_of_the_parent():
    """``create`` (``ir_actions.py:712-718``): con ``parent_id`` el hijo toma
    el ``model_id`` y los ``group_ids`` del padre."""
    user, env = _system_env('ir.actions.server')
    group = _group('base.group_user')
    with user_scope(user.pk):
        parent = env.create({'name': 'Parent', 'model_name': 'res.partner',
                             'state': 'multi', 'group_ids': [group.pk]})
        child = env.create({'name': 'Child', 'model_name': 'res.users',
                            'state': 'code', 'parent_id': parent.id})
    row = IrActionsServer.objects.get(pk=child.id)
    assert row.model_name == 'res.partner'
    assert list(row.group_ids.values_list('pk', flat=True)) == [group.pk]


def test_creating_with_code_records_the_first_revision():
    """``create`` (``ir_actions.py:720-726``)."""
    user, env = _system_env('ir.actions.server')
    with user_scope(user.pk):
        action = env.create({'name': 'Coded', 'model_name': 'res.partner',
                             'state': 'code', 'code': 'records = records'})
    assert list(IrActionsServerHistory.objects.filter(
        action_id=action.id).values_list('code', flat=True)) == [
            'records = records']


def test_creating_without_code_records_no_revision():
    user, env = _system_env('ir.actions.server')
    with user_scope(user.pk):
        action = env.create({'name': 'Plain', 'model_name': 'res.partner',
                             'state': 'object_write'})
    assert not IrActionsServerHistory.objects.filter(
        action_id=action.id).exists()


def test_writing_new_code_records_a_revision_and_same_code_does_not():
    """``write`` (``ir_actions.py:730-733``)."""
    user, env = _system_env('ir.actions.server')
    with user_scope(user.pk):
        action = env.create({'name': 'Edited', 'model_name': 'res.partner',
                             'state': 'code', 'code': 'a = 1'})
        action.write({'code': 'a = 2'})
        action.write({'code': 'a = 2'})
    assert sorted(IrActionsServerHistory.objects.filter(
        action_id=action.id).values_list('code', flat=True)) == [
            'a = 1', 'a = 2']
