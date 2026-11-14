"""Los comodelos pequeños de ``hr`` sobre ``BaseModel`` (grupo B).

≙ ``odoo19c: addons/hr/models/{hr_payroll_structure_type,hr_contract_type,
hr_employee_category,hr_departure_reason,hr_work_location}.py``: los cinco
son ``models.Model``, o sea ``BaseModel``. Su seguridad ya la carga el
manifiesto de ``hr``. Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/hr-comodels-basemodel.md``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db

MODELS = ('hr.payroll.structure.type', 'hr.contract.type',
          'hr.employee.category', 'hr.departure.reason', 'hr.work.location')


@pytest.mark.parametrize('name', MODELS)
def test_every_comodel_is_a_base_model(name):
    assert issubclass(MODELS_BY_NAME[name], BaseModel)


def _internal_user():
    group = MODELS_BY_NAME['res.groups'].objects.get(
        pk=IrModelData.objects.get(module='base', name='group_user').res_id)
    with sudo():
        user = get_user_model().objects.create_user(
            login='hr-comodels-internal', password=None, name='i')
    user.group_ids.add(group)
    return user


@pytest.mark.parametrize('name', MODELS)
def test_an_internal_user_cannot_create_them(name):
    """La ACL de ``hr`` sólo le concede a RR. HH. crear estos catálogos."""
    user = _internal_user()
    with user_scope(user.pk):
        with pytest.raises(AccessError):
            Environment(uid=user.pk)[name].check_access('create')
