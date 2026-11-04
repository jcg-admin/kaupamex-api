"""``BaseModel._filter_access_rules_python`` — ≙ ``odoo19c:
odoo/orm/models.py:4190-4192``. TASK-API-0485.

Obsoleto desde 18.0: avisa y devuelve lo mismo que ``_filtered_access``.
"""
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_filter_access_rules_python_is_filtered_access(env):
    records = env['test_orm.foo'].create([{'value1': 1}, {'value1': 2}])
    with pytest.warns(DeprecationWarning, match='_filtered_access'):
        filtered = records._filter_access_rules_python('read')
    assert filtered == records._filtered_access('read')
