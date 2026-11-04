"""``BaseModel.check_access`` — ≙ ``odoo19c: odoo/orm/models.py:4100-4115``.
TASK-API-0485.

Levanta ``AccessError`` si la operación está prohibida; bajo elevación no
comprueba nada.
"""
import pytest

from exceptions import AccessError
from orm.environments import Environment
from tests.factories.user_factory import UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _plain_user():
    """Un usuario sin ACL sobre ``test_orm.foo``: ``SUPERUSER_ID`` eleva
    siempre (``odoo19c: odoo/orm/environments.py:66-67``)."""
    return Environment(None, UserFactory().pk, {})


def test_check_access_elevated_passes(env):
    record = env['test_orm.foo'].create({'value1': 1})
    assert record.check_access('unlink') is None


def test_check_access_refuses_a_user_without_acl(env):
    record = env['test_orm.foo'].create({'value1': 1})
    with _plain_user() as plain:
        with pytest.raises(AccessError):
            record.with_env(plain).check_access('read')
