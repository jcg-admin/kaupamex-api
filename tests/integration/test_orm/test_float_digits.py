"""Un ``Float`` con ``digits`` es una columna ``numeric`` que se lee como
``float`` — ≙ ``Float._column_type`` (``odoo19c: odoo/orm/
fields_numeric.py:125-133``) y la expectativa de ``test_schema.py`` sobre
``test_orm.mixed.number``. Cierra :ref:`h-api-1131`.
"""

import pytest
from django.db import connection

import fields

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _column_type(table, column):
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT data_type FROM information_schema.columns '
            'WHERE table_name = %s AND column_name = %s', [table, column])
        return cursor.fetchone()[0]


def test_a_float_with_digits_is_a_numeric_column():
    assert _column_type('test_orm_mixed', 'number') == 'numeric'


def test_the_column_type_follows_the_digits():
    assert fields.Float().column_type == ('float8', 'float8')
    assert fields.Float(digits=(10, 2)).column_type == ('numeric', 'numeric')
    assert fields.Float(digits='Product Price').column_type == (
        'numeric', 'numeric')


def test_the_numeric_column_reads_back_as_a_float(env):
    record = env['test_orm.mixed'].create({'number': 2.5})
    value = env['test_orm.mixed'].browse(record.ids).number
    reread = type(record)._base_manager.get(pk=record.pk).number
    assert type(value) is float and value == 2.5
    assert type(reread) is float and reread == 2.5


def test_the_value_is_rounded_to_its_digits(env):
    """``Float.convert_to_column`` redondea a la escala de ``digits``
    (``fields_numeric.py:155-163``)."""
    record = env['test_orm.mixed'].create({'number': 2.345})
    reread = type(record)._base_manager.get(pk=record.pk).number
    assert reread == 2.35
