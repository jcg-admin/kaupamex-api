"""``increment_fields_skiplock`` — ≙ ``odoo19c: odoo/tools/sql.py:672-705``.

Incrementa sin bloquear: una fila tomada por otra transacción se salta, y el
retorno dice si se incrementó alguna.
"""

import pytest

from tools.sql import increment_fields_skiplock

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_increments_from_null_and_from_a_value(env):
    Foo = env['test_orm.foo']
    empty, five = Foo.create([{}, {'value1': 5}])
    assert increment_fields_skiplock(empty | five, 'value1') is True
    (empty | five).invalidate_recordset()
    assert (empty.value1, five.value1) == (1, 6)


def test_an_empty_recordset_does_nothing(env):
    assert increment_fields_skiplock(env['test_orm.foo'], 'value1') is False


def test_a_non_integer_field_is_rejected(env):
    record = env['test_orm.foo'].create({})
    with pytest.raises(AssertionError):
        increment_fields_skiplock(record, 'name')
