"""``onboarding`` sobre ``BaseModel`` y con la ACL de la referencia.

≙ ``odoo19c: addons/onboarding/models/*.py`` (los cuatro modelos son
``BaseModel`` con sus atributos de clase) y ``odoo19c:
addons/onboarding/security/ir.model.access.csv`` (doce filas: sin permiso
para todos y para ``base.group_user``; los cuatro para
``base.group_system``). Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-onboarding.md``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelAccess, IrModelData
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db

HEADERS = {
    'onboarding.onboarding': {
        '_description': 'Onboarding', '_order': 'sequence asc, id desc'},
    'onboarding.onboarding.step': {
        '_description': 'Onboarding Step', '_order': 'sequence asc, id asc',
        '_rec_name': 'title'},
    'onboarding.progress': {
        '_description': 'Onboarding Progress Tracker'},
    'onboarding.progress.step': {
        '_description': 'Onboarding Progress Step Tracker'},
}


def _internal_user():
    group = MODELS_BY_NAME['res.groups'].objects.get(
        pk=IrModelData.objects.get(module='base', name='group_user').res_id)
    with sudo():
        user = get_user_model().objects.create_user(
            login='onboarding-acl-internal', password=None, name='interno')
    user.group_ids.add(group)
    return user


@pytest.mark.parametrize('name', sorted(HEADERS))
def test_every_onboarding_model_is_a_base_model(name):
    model = MODELS_BY_NAME[name]
    assert issubclass(model, BaseModel)
    assert model.__dict__['_name'] == name
    for attribute, value in HEADERS[name].items():
        assert model.__dict__[attribute] == value, attribute


def test_the_acl_is_the_reference_csv_with_its_external_ids():
    xmlids = IrModelData.objects.filter(module='onboarding',
                                        model='ir.model.access')
    assert xmlids.count() == 12
    row = IrModelAccess.objects.get(
        pk=xmlids.get(name='access_onboarding_step_manager').res_id)
    perms = (row.perm_read, row.perm_write, row.perm_create, row.perm_unlink)
    assert perms == (True, True, True, True)


def test_an_internal_user_cannot_read_a_step():
    user = _internal_user()
    with user_scope(user.pk):
        steps = Environment(uid=user.pk)['onboarding.onboarding.step']
        with pytest.raises(AccessError):
            steps.check_access('read')
