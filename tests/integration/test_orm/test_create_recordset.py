"""El resultado de ``create`` es un recordset que escribe — H-API-1123.

≙ ``odoo19c: odoo/orm/models.py:4611-4770`` (``create`` devuelve el recordset
de ``BaseModel``) y ``odoo/orm/fields.py:1807-1841`` (``Field.__set__``
escribe). Antes de ``DefaultGetMixin._create_result`` el resultado era un
``QuerySet`` y ``rs.name = 'Bar'`` se quedaba como atributo suyo, sin tocar la
base y sin error.
"""

import pytest

from addons.test_orm.models.test_orm import TestOrmCategory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_create_returns_the_native_recordset_in_order(env):
    records = env['test_orm.category'].create(
        [{'name': 'First'}, {'name': 'Second'}])
    assert isinstance(records, TestOrmCategory)
    assert [record.name for record in records] == ['First', 'Second']
    assert len(records.ids) == 2


def test_assigning_a_field_on_the_created_record_is_written(env):
    record = env['test_orm.category'].create({'name': 'Foo'})
    record.name = 'Bar'
    env.flush_all()
    assert TestOrmCategory.objects.get(pk=record.id).name == 'Bar'


def test_an_empty_create_is_an_empty_recordset(env):
    records = env['test_orm.category'].create([])
    assert isinstance(records, TestOrmCategory)
    assert not records
