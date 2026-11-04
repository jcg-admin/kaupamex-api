"""``BaseModel.check_access_rights`` — ≙ ``odoo19c:
odoo/orm/models.py:4161-4173``. TASK-API-0485.

Obsoleto desde 18.0: avisa y delega en ``check_access`` (que levanta) o en
``has_access`` (que responde) sobre el recordset vacío del modelo.
"""
import pytest

from exceptions import AccessError
from orm.environments import Environment
from tests.factories.user_factory import UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_check_access_rights_raising_delegates_to_check_access(env):
    Foo = env['test_orm.foo']
    with pytest.warns(DeprecationWarning, match='check_access'):
        assert Foo.check_access_rights('read') is None


def test_check_access_rights_without_raising_answers_has_access(env):
    Foo = env['test_orm.foo']
    expected = Foo.browse().has_access('unlink')
    with pytest.warns(DeprecationWarning, match='check_access'):
        assert Foo.check_access_rights(
            'unlink', raise_exception=False) is expected


def test_check_access_rights_follows_a_denial(env):
    with Environment(None, UserFactory().pk, {}) as plain:
        Foo = plain['test_orm.foo']
        with pytest.warns(DeprecationWarning):
            assert Foo.check_access_rights(
                'read', raise_exception=False) is False
        with pytest.warns(DeprecationWarning), pytest.raises(AccessError):
            Foo.check_access_rights('read')
