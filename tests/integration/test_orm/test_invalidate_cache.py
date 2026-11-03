"""``invalidate_recordset`` / ``invalidate_model`` — ≙ ``odoo19c:
odoo/orm/models.py`` (``invalidate_model``, ``invalidate_recordset``,
``_invalidate_cache``).

La caché deja de creerse lo que guardaba: la siguiente lectura va a la base.
"""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _write_behind_the_cache(record, value):
    type(record).objects.filter(pk=record.pk).update(value1=value)


def test_invalidate_recordset_drops_only_its_rows(env):
    Foo = env['test_orm.foo']
    one, two = Foo.create([{'value1': 1}, {'value1': 2}])
    assert (one.value1, two.value1) == (1, 2)
    _write_behind_the_cache(one, 10)
    _write_behind_the_cache(two, 20)
    one.invalidate_recordset(['value1'])
    assert env['test_orm.foo'].browse(one.ids).value1 == 10
    assert env['test_orm.foo'].browse(two.ids).value1 == 2


def test_invalidate_model_drops_every_row(env):
    Foo = env['test_orm.foo']
    one, two = Foo.create([{'value1': 1}, {'value1': 2}])
    assert (one.value1, two.value1) == (1, 2)
    _write_behind_the_cache(one, 10)
    _write_behind_the_cache(two, 20)
    Foo.invalidate_model(['value1'])
    assert [r.value1 for r in env['test_orm.foo'].browse((one | two).ids)] == [10, 20]


def test_invalidate_flushes_pending_writes_first(env):
    record = env['test_orm.foo'].create({'value1': 1})
    env.transaction.field_dirty[record._fields['value1']].add(record.id)
    record.env.transaction.field_data[record._fields['value1']][record.id] = 7
    record.invalidate_recordset(['value1'])
    assert type(record).objects.get(pk=record.pk).value1 == 7


def test_reading_from_the_database_does_not_mark_the_field_dirty(env):
    """≙ ``Field.__get__`` → ``_fetch_field`` (``odoo19c: odoo/orm/fields.py``):
    leer una columna llena la caché **sin** ensuciarla. Antes, la recarga de
    Django pasaba por la escritura del ORM y el campo quedaba sucio, así que
    el siguiente volcado reescribía la base con lo leído."""
    record = env['test_orm.foo'].create({'value1': 1})
    field = record._fields['value1']
    reread = env['test_orm.foo'].browse(record.ids)
    assert reread.value1 == 1
    assert record.id not in (env.transaction.field_dirty.get(field) or ())


def test_flush_recordset_takes_several_rows(env):
    """≙ ``flush_recordset`` (``odoo19c: odoo/orm/models.py:6367-6384``) sobre
    un recordset de N filas: antes moría con *Expected singleton* porque
    ``as_record_list`` lo trataba como una sola fila."""
    one, two = env['test_orm.foo'].create([{'value1': 1}, {'value1': 2}])
    field = one._fields['value1']
    env.transaction.field_data[field][two.id] = 9
    env.transaction.field_dirty[field].add(two.id)
    (one | two).flush_recordset(['value1'])
    assert type(two).objects.get(pk=two.pk).value1 == 9
    assert two.id not in (env.transaction.field_dirty.get(field) or ())
