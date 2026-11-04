"""``BaseModel.action_archive`` — ≙ ``odoo19c:
odoo/orm/models.py:5796-5805``. TASK-API-0485.

Pone ``active = False`` en los registros activos de ``self``; los ya
archivados no se escriben.
"""
import pytest

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
