"""``resource`` sobre ``BaseModel`` y con la seguridad de la referencia.

≙ ``odoo19c: addons/resource/models/*.py`` (los cuatro modelos son
``BaseModel``) y ``odoo19c: addons/resource/security/``
(``ir.model.access.csv``: ocho filas; ``resource_security.xml``: cinco
reglas). Los dos archivos son copia fiel y los carga el ciclo de instalación
desde el manifiesto. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-resource.md``.
"""
import datetime

import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db

MODELS = ('resource.calendar', 'resource.calendar.attendance',
          'resource.calendar.leaves', 'resource.resource')
START = datetime.datetime(2026, 11, 2, 8, tzinfo=datetime.timezone.utc)
END = datetime.datetime(2026, 11, 2, 17, tzinfo=datetime.timezone.utc)


def _internal_user(login):
    group = MODELS_BY_NAME['res.groups'].objects.get(
        pk=IrModelData.objects.get(module='base', name='group_user').res_id)
    with sudo():
        user = get_user_model().objects.create_user(
            login=login, password=None, name=login)
    user.group_ids.add(group)
    return user


def _leaves(owner, other):
    Resource = MODELS_BY_NAME['resource.resource']
    Leaves = MODELS_BY_NAME['resource.calendar.leaves']
    with sudo():
        mine = Resource.objects.create(name='Mío', user=owner)
        theirs = Resource.objects.create(name='Ajeno', user=other)
        made = {key: Leaves.objects.create(
            name=key, resource=resource, date_from=START, date_to=END)
            for key, resource in (('global', None), ('mine', mine),
                                  ('theirs', theirs))}
    return {key: leave.pk for key, leave in made.items()}


@pytest.mark.parametrize('name', MODELS)
def test_every_resource_model_is_a_base_model(name):
    assert issubclass(MODELS_BY_NAME[name], BaseModel)


def test_the_acl_and_rules_carry_their_external_ids():
    data = IrModelData.objects.filter(module='resource')
    assert data.filter(model='base.IrModelAccess').count() == 8
    assert data.filter(model='base.IrRule').count() == 5


def test_an_internal_user_reads_calendars_but_does_not_write_them():
    user = _internal_user('resource-internal')
    with user_scope(user.pk):
        calendars = Environment(uid=user.pk)['resource.calendar']
        calendars.check_access('read')
        with pytest.raises(AccessError):
            calendars.check_access('write')


def test_an_internal_user_reads_global_and_own_leaves_only():
    user = _internal_user('resource-reader')
    other = _internal_user('resource-other')
    ids = _leaves(user, other)
    with user_scope(user.pk):
        leaves = Environment(uid=user.pk)['resource.calendar.leaves']
        seen = set(leaves.search([('id', 'in', list(ids.values()))]).ids)
    assert seen == {ids['global'], ids['mine']}


def test_an_internal_user_modifies_own_leave_but_not_a_global_one():
    user = _internal_user('resource-writer')
    other = _internal_user('resource-someone')
    ids = _leaves(user, other)
    with user_scope(user.pk):
        leaves = Environment(uid=user.pk)['resource.calendar.leaves']
        leaves.browse(ids['mine']).write({'name': 'Propia'})
        with pytest.raises(AccessError):
            leaves.browse(ids['global']).write({'name': 'Global'})
