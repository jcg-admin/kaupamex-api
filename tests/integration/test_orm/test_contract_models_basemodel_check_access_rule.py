"""``BaseModel.check_access_rule`` — ≙ ``odoo19c:
odoo/orm/models.py:4175-4183``. TASK-API-0485.

Obsoleto desde 18.0: avisa y delega en ``check_access``.
"""
import pytest

from exceptions import AccessError
from orm.environments import Environment
from tests.factories.user_factory import UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_check_access_rule_warns_and_checks(env):
    record = env['test_orm.foo'].create({'value1': 1})
    with pytest.warns(DeprecationWarning, match='check_access'):
        assert record.check_access_rule('read') is None


def test_check_access_rule_follows_a_denial(env):
    record = env['test_orm.foo'].create({'value1': 1})
    with Environment(None, UserFactory().pk, {}) as plain:
        with pytest.warns(DeprecationWarning), pytest.raises(AccessError):
            record.with_env(plain).check_access_rule('read')
