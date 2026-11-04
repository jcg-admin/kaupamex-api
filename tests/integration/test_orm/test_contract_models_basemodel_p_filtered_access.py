"""``BaseModel._filtered_access`` — ≙ ``odoo19c:
odoo/orm/models.py:4123-4129``.
TASK-API-0485.

El subconjunto permitido: ``self`` menos los prohibidos.
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


def test_filtered_access_elevated_keeps_everything(env):
    records = env['test_orm.foo'].create([{'value1': 1}, {'value1': 2}])
    assert records._filtered_access('read') == records


def test_filtered_access_without_acl_keeps_nothing(env):
    records = env['test_orm.foo'].create([{'value1': 1}, {'value1': 2}])
    with _plain_user() as plain:
        assert not records.with_env(plain)._filtered_access('read')
