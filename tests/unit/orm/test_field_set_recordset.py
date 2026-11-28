"""Asignar un campo sobre un recordset de varios registros.

≙ ``Field.__set__`` (``odoo19c: odoo/orm/fields.py:1807-1841``): los
registros persistidos van a ``records.write({name: value})``; los nuevos
reciben la asignación sin lógica de negocio. Diseño:
``designs/ir-module-group-a.md``.
"""

import pytest

from addons.base.models import IrModuleCategory
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _categories():
    return Environment(uid=SUPERUSER_ID)['ir.module.category']


def test_persisted_records_are_written_together():
    model = _categories()
    records = model.create([{'name': 'fs-a'}, {'name': 'fs-b'}])
    records.sequence = 42
    assert sorted(IrModuleCategory.objects.filter(
        pk__in=records.ids).values_list('sequence', flat=True)) == [42, 42]


def test_new_records_take_the_value_in_cache():
    model = _categories()
    records = model.new({'name': 'fs-new-a'}) | model.new({'name': 'fs-new-b'})
    records.sequence = 7
    assert [record.sequence for record in records] == [7, 7]
    assert not IrModuleCategory.objects.filter(
        name__startswith='fs-new-').exists()
