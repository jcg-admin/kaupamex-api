"""``BaseModel.toggle_active`` — ≙ ``odoo19c:
odoo/orm/models.py:5788-5794``. TASK-API-0485.

Obsoleto desde 19.0: invierte ``active`` en cada registro.
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


def test_toggle_active_inverts_each_record(env):
    records = _records(env)
    with pytest.warns(DeprecationWarning, match="action_archive"):
        records.toggle_active()
    assert _stored_active(records) == {"on": False, "off": True}
