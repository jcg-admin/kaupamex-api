"""``BaseModel.action_unarchive`` — ≙ ``odoo19c:
odoo/orm/models.py:5807-5816``. TASK-API-0485.

Pone ``active = True`` en los registros archivados de ``self``.
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


def test_action_unarchive_activates_the_archived_ones(env):
    records = _records(env)
    records.action_unarchive()
    assert _stored_active(records) == {"on": True, "off": True}
