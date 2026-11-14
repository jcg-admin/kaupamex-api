"""``hr_work_entry`` sobre ``BaseModel`` y con la seguridad de la referencia.

≙ ``odoo19c: addons/hr_work_entry/models/*.py`` (los tres modelos son
``BaseModel``) y ``odoo19c: addons/hr_work_entry/security/``. Los dos
archivos son copia fiel, salvo las omisiones que declaran su cabecera y el
manifiesto, y los carga el ciclo de instalación. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-hr-work-entry.md``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db

MODELS = ('hr.work.entry', 'hr.work.entry.type',
          'hr.user.work.entry.employee')


def _group(module, name):
    return MODELS_BY_NAME['res.groups'].objects.get(
        pk=IrModelData.objects.get(module=module, name=name).res_id)


def _user(login, *groups):
    with sudo():
        user = get_user_model().objects.create_user(
            login=login, password=None, name=login)
    for group in groups:
        user.group_ids.add(group)
    return user


@pytest.mark.parametrize('name', MODELS)
def test_every_work_entry_model_is_a_base_model(name):
    assert issubclass(MODELS_BY_NAME[name], BaseModel)


def test_the_acl_and_rules_carry_their_external_ids():
    data = IrModelData.objects.filter(module='hr_work_entry')
    assert data.filter(model='base.IrModelAccess').count() == 5
    assert set(data.filter(model='base.IrRule').values_list(
        'name', flat=True)) == {'hr_user_work_entry_employee',
                                'ir_rule_hr_work_entry_multi_company'}


def test_an_officer_creates_entries_but_cannot_delete_them():
    user = _user('work-entry-officer', _group('base', 'group_user'),
                 _group('hr', 'group_hr_user'))
    with user_scope(user.pk):
        environment = Environment(uid=user.pk)
        environment['hr.work.entry'].check_access('create')
        with pytest.raises(AccessError):
            environment['hr.work.entry'].check_access('unlink')
        environment['hr.work.entry.type'].check_access('read')
        with pytest.raises(AccessError):
            environment['hr.work.entry.type'].check_access('write')


def test_an_internal_user_has_no_access_to_work_entries():
    user = _user('work-entry-internal', _group('base', 'group_user'))
    with user_scope(user.pk):
        with pytest.raises(AccessError):
            Environment(uid=user.pk)['hr.work.entry'].check_access('read')
