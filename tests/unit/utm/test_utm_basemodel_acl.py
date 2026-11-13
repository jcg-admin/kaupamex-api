"""``utm`` sobre ``BaseModel`` y con la ACL de la referencia.

≙ ``odoo19c: addons/utm/models/*.py`` (los cinco modelos son ``BaseModel``)
y ``odoo19c: addons/utm/security/ir.model.access.csv`` (diez filas: CRUD sin
borrado para ``base.group_user`` en campaña, medio y fuente; sólo lectura en
etapa y etiqueta; todo para ``base.group_system``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-utm.md``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData
from addons.utm.security.ir_model_access import _ACCESS
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db

UTM = ('utm.campaign', 'utm.medium', 'utm.source', 'utm.stage', 'utm.tag')


def _internal_user():
    group = MODELS_BY_NAME['res.groups'].objects.get(
        pk=IrModelData.objects.get(module='base', name='group_user').res_id)
    with sudo():
        user = get_user_model().objects.create_user(
            login='utm-acl-internal', password=None, name='interno')
    user.group_ids.add(group)
    return user


@pytest.mark.parametrize('name', UTM)
def test_every_utm_model_is_a_base_model(name):
    assert issubclass(MODELS_BY_NAME[name], BaseModel)


def test_the_acl_is_the_reference_csv():
    assert len(_ACCESS) == 10
    stage = {perms for _, label, group, perms in _ACCESS
             if label == 'utm.UtmStage' and group == 'group_user'}
    assert stage == {(1, 0, 0, 0)}


def test_an_internal_user_creates_a_source_but_cannot_delete_it():
    user = _internal_user()
    with user_scope(user.pk):
        sources = Environment(uid=user.pk)['utm.source']
        source = sources.create({'name': 'Boletín'})
        assert source.name == 'Boletín'
        with pytest.raises(AccessError):
            source.unlink()


def test_an_internal_user_only_reads_tags():
    user = _internal_user()
    with user_scope(user.pk):
        tags = Environment(uid=user.pk)['utm.tag']
        tags.check_access('read')
        with pytest.raises(AccessError):
            tags.check_access('create')
