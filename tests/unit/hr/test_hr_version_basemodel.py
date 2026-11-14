"""``hr.version`` sobre ``BaseModel``.

≙ ``odoo19c: addons/hr/models/hr_version.py`` (``models.Model``) y su ACL en
``hr/security/ir.model.access.csv``: sólo RR. HH. lo lee. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
hr-version-basemodel.md``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


def _user(login, *xmlids):
    with sudo():
        user = get_user_model().objects.create_user(
            login=login, password=None, name=login)
    for xmlid in xmlids:
        module, name = xmlid.split('.')
        user.group_ids.add(MODELS_BY_NAME['res.groups'].objects.get(
            pk=IrModelData.objects.get(module=module, name=name).res_id))
    return user


def test_the_version_is_a_base_model():
    assert issubclass(MODELS_BY_NAME['hr.version'], BaseModel)


def test_an_internal_user_cannot_read_versions():
    user = _user('version-internal', 'base.group_user')
    with user_scope(user.pk):
        with pytest.raises(AccessError):
            Environment(uid=user.pk)['hr.version'].check_access('read')


def test_an_hr_officer_reads_versions():
    user = _user('version-officer', 'base.group_user', 'hr.group_hr_user')
    with user_scope(user.pk):
        Environment(uid=user.pk)['hr.version'].check_access('read')
