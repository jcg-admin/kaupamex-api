"""``BaseModel.has_access`` — ≙ ``odoo19c: odoo/orm/models.py:4117-4121``.
TASK-API-0485.

El mismo veredicto que ``check_access``, como booleano.
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


def test_has_access_elevated_is_true(env):
    record = env['test_orm.foo'].create({'value1': 1})
    assert record.has_access('write') is True


def test_has_access_without_acl_is_false(env):
    record = env['test_orm.foo'].create({'value1': 1})
    with _plain_user() as plain:
        assert record.with_env(plain).has_access('read') is False
