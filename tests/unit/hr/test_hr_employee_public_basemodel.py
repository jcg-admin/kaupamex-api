"""``hr.employee.public`` sobre ``BaseModel``.

≙ ``odoo19c: addons/hr/models/hr_employee_public.py`` (``models.Model`` con
``_auto = False``) y su fila de ACL: un usuario interno sólo lee. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
hr-employee-public-basemodel.md``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


def _internal_user():
    group = MODELS_BY_NAME['res.groups'].objects.get(
        pk=IrModelData.objects.get(module='base', name='group_user').res_id)
    with sudo():
        user = get_user_model().objects.create_user(
            login='public-employee-reader', password=None, name='r')
    user.group_ids.add(group)
    return user


def test_the_public_employee_is_a_base_model():
    assert issubclass(MODELS_BY_NAME['hr.employee.public'], BaseModel)


def test_an_internal_user_reads_but_does_not_write():
    user = _internal_user()
    with user_scope(user.pk):
        public = Environment(uid=user.pk)['hr.employee.public']
        public.check_access('read')
        with pytest.raises(AccessError):
            public.check_access('write')
