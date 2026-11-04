"""``BaseModel._check_access`` — ≙ ``odoo19c: odoo/orm/models.py:4127-4149``.
TASK-API-0485.

Devuelve ``None`` si se puede, o el par (prohibidos, fábrica de error);
la ACL del modelo se evalúa antes que las reglas de fila.
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


def test_check_access_private_allows_when_permitted(env):
    record = env['test_orm.foo'].create({'value1': 1})
    assert record._check_access('read') is None


def test_check_access_private_names_the_forbidden_records(env):
    record = env['test_orm.foo'].create({'value1': 1})
    with _plain_user() as plain:
        forbidden, make_error = record.with_env(plain)._check_access('read')
    assert forbidden.ids == record.ids
    assert isinstance(make_error(), AccessError)
