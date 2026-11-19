"""``authz_totp`` sobre ``BaseModel``, con la seguridad de la referencia.

≙ ``odoo19c: addons/auth_totp/models/auth_totp.py:15-16``
(``auth_totp.device``), ``odoo19c:
addons/auth_totp/models/auth_totp_rate_limit_log.py:5`` y los dos archivos de
``odoo19c: addons/auth_totp/security/``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-authz-totp.md``.

*Métrica:* el tipo de cada modelo, las filas cargadas con el identificador
externo del módulo y el registro de intentos de un usuario interno.
*Ciega a:* el asistente de alta (``auth_totp.wizard``), que este árbol no
porta como modelo.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelAccess, IrModelData, IrRule
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db

MODELS = {
    'auth_totp.device': 'Authentication Device',
    'auth.totp.rate.limit.log': 'TOTP rate limit logs',
}


@pytest.fixture
def internal_user(db):
    group = MODELS_BY_NAME['res.groups'].objects.get(
        pk=IrModelData.objects.get(module='base', name='group_user').res_id)
    with sudo():
        user = get_user_model().objects.create_user(
            login='totp-acl-internal', password=None, name='interno')
    user.group_ids.add(group)
    return user


@pytest.mark.parametrize('name', sorted(MODELS))
def test_each_model_is_a_base_model_with_its_description(name):
    model = MODELS_BY_NAME[name]
    assert issubclass(model, BaseModel)
    assert model.__dict__['_description'] == MODELS[name]


def test_the_acl_is_the_reference_csv():
    xmlids = set(IrModelData.objects.filter(
        module='authz_totp', model='base.IrModelAccess',
    ).values_list('name', flat=True))
    assert xmlids == {
        'access_auth_totp_device_access_employee',
        'access_auth_totp_device_access_portal',
        'access_auth_totp_rate_limit_log',
    }
    log = IrModelAccess.objects.get(pk=IrModelData.objects.get(
        module='authz_totp', name='access_auth_totp_rate_limit_log').res_id)
    assert (log.perm_read, log.perm_write, log.perm_create,
            log.perm_unlink) == (False, False, False, False)


def test_the_device_rules_are_the_reference_xml():
    """Sin las dos del asistente, que no tiene modelo (manifiesto)."""
    names = set(IrModelData.objects.filter(
        module='authz_totp', model='base.IrRule',
    ).values_list('name', flat=True))
    assert names == {'api_key_public', 'api_key_user', 'api_key_admin'}
    rule = IrRule.objects.get(pk=IrModelData.objects.get(
        module='authz_totp', name='api_key_user').res_id)
    assert rule.domain_force == "[('user_id', '=', user.id)]"


def test_an_internal_user_cannot_read_the_rate_limit_log(internal_user):
    with user_scope(internal_user.pk):
        logs = Environment(uid=internal_user.pk)['auth.totp.rate.limit.log']
        with pytest.raises(AccessError):
            logs.check_access('read')


def test_an_internal_user_still_counts_its_attempts(internal_user):
    """≙ ``_totp_rate_limit`` (``res_users.py:118-142``): la fuente escribe
    el registro con ``sudo()``; aquí ``objects`` no pasa por la ACL. Guarda
    de que la ACL vacía del registro no rompe el conteo."""
    with user_scope(internal_user.pk):
        internal_user._totp_rate_limit('code_check')
        internal_user._totp_rate_limit_purge('code_check')
