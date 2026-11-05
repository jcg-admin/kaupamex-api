"""``BaseModel.action_archive`` — ≙ ``odoo19c:
odoo/orm/models.py:5796-5805``. TASK-API-0485.

Pone ``active = False`` en los registros activos de ``self``; los ya
archivados no se escriben.
"""
import pytest

from exceptions import AccessError
from orm.environments import Environment
from tests.factories.user_factory import UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _records(env):
    Model = env["test_orm.model_active_field"]
    return Model.create([{"name": "on", "active": True},
                         {"name": "off", "active": False}])


def _stored_active(records):
    rows = type(records)._default_manager.filter(pk__in=records.ids)
    return dict(rows.values_list("name", "active"))


def test_action_archive_deactivates_the_active_ones(env):
    records = _records(env)
    records.action_archive()
    assert _stored_active(records) == {"on": False, "off": False}


def test_action_archive_needs_an_active_field(env):
    record = env["test_orm.foo"].create({"value1": 1})
    with pytest.raises(AssertionError, match="No 'active' field"):
        record.action_archive()


def test_action_archive_of_an_empty_recordset_is_a_no_op(env):
    empty = env["test_orm.model_active_field"].browse()
    assert empty.action_archive() is None


def test_action_archive_returns_nothing(env):
    assert _records(env).action_archive() is None


def test_action_archive_writes_through_the_access_check(env):
    from_superuser = _records(env)
    with Environment(None, UserFactory().pk, {}) as plain:
        with pytest.raises(AccessError):
            from_superuser.with_env(plain).action_archive()
    assert _stored_active(from_superuser) == {"on": True, "off": False}


def test_action_archive_deactivates_every_active_record(env):
    Model = env["test_orm.model_active_field"]
    records = Model.create([{"name": "a", "active": True},
                            {"name": "b", "active": True}])
    records.action_archive()
    assert _stored_active(records) == {"a": False, "b": False}
