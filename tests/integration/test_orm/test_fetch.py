"""``BaseModel.fetch`` y su cadena — ≙ ``odoo19c: odoo/orm/models.py``
(``fetch`` :3775-3818, ``_determine_fields_to_fetch`` :3820-3877,
``_fetch_query`` :3879-3942, ``_as_query`` :5396-5404). TASK-API-0399.

Cada grupo es una unidad del plan y su ``verify`` lo selecciona por nombre:
``as_query``, ``fields_to_fetch``, ``fetch_query`` y ``fetch_records``.
"""
import pytest

from tools.sql import SQL

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _write_behind_the_cache(record, value):
    type(record).objects.filter(pk=record.pk).update(value1=value)


def _ids_selected(records, query):
    sql = query.select(SQL.identifier(records._table, 'id'))
    return [row[0] for row in records.env.execute_query(sql)]


# -- _as_query ---------------------------------------------------------------

def test_as_query_returns_the_ids_in_the_recordset_order(env):
    one, two = env['test_orm.foo'].create([{'value1': 1}, {'value1': 2}])
    records = env['test_orm.foo'].browse([two.id, one.id])
    assert _ids_selected(records, records._as_query()) == [two.id, one.id]


def test_as_query_of_an_empty_recordset_selects_nothing(env):
    empty = env['test_orm.foo'].browse()
    assert _ids_selected(empty, empty._as_query()) == []


def test_as_query_unordered_returns_the_same_set(env):
    one, two = env['test_orm.foo'].create([{'value1': 1}, {'value1': 2}])
    records = env['test_orm.foo'].browse([two.id, one.id])
    assert sorted(_ids_selected(records, records._as_query(ordered=False))) \
        == sorted([one.id, two.id])


# -- _determine_fields_to_fetch ----------------------------------------------

def test_fields_to_fetch_none_means_every_prefetched_readable_field(env):
    Foo = env['test_orm.foo']
    names = {field.name for field in Foo._determine_fields_to_fetch(None)}
    assert {'name', 'value1', 'value2', 'text'} <= names


def test_fields_to_fetch_empty_is_empty(env):
    assert env['test_orm.foo']._determine_fields_to_fetch([]) == []


def test_fields_to_fetch_rejects_an_unknown_field(env):
    with pytest.raises(ValueError, match='Invalid field'):
        env['test_orm.foo']._determine_fields_to_fetch(['nope'])


def test_fields_to_fetch_skips_what_is_in_cache_when_asked(env):
    record = env['test_orm.foo'].create({'value1': 1})
    assert record.value1 == 1
    assert record._determine_fields_to_fetch(
        ['value1'], ignore_when_in_cache=True) == []
    assert [field.name for field in record._determine_fields_to_fetch(
        ['value1'])] == ['value1']


def test_fields_to_fetch_follows_a_non_stored_compute_to_its_column(env):
    Category = env['test_orm.category']
    names = [field.name for field in
             Category._determine_fields_to_fetch(['depth'])]
    assert names == ['parent_path']


# -- _fetch_query ------------------------------------------------------------

def test_fetch_query_puts_the_column_values_in_cache(env):
    record = env['test_orm.foo'].create({'value1': 1})
    record.invalidate_recordset(['value1'])
    fetched = record._fetch_query(record._as_query(),
                                  [record._fields['value1']])
    assert fetched.ids == record.ids
    _write_behind_the_cache(record, 10)
    assert record.value1 == 1, 'the value came from the fetch, not the read'


def test_fetch_query_of_rows_that_do_not_exist_is_empty(env):
    record = env['test_orm.foo'].create({'value1': 1})
    ghost = env['test_orm.foo'].browse([record.id + 100000])
    fetched = ghost._fetch_query(ghost._as_query(),
                                 [ghost._fields['value1']])
    assert not fetched


# -- fetch -------------------------------------------------------------------

def test_fetch_records_loads_the_requested_fields_in_cache(env):
    record = env['test_orm.foo'].create({'value1': 1})
    record.invalidate_recordset(['value1'])
    record.fetch(['value1'])
    _write_behind_the_cache(record, 10)
    assert record.value1 == 1


def test_fetch_records_on_an_empty_request_does_nothing(env):
    record = env['test_orm.foo'].create({'value1': 1})
    record.invalidate_recordset(['value1'])
    record.fetch([])
    _write_behind_the_cache(record, 10)
    assert record.value1 == 10, 'nothing fetched: the read goes to the db'


def test_fetch_records_ignores_new_records(env):
    new = env['test_orm.foo'].new({'value1': 3})
    assert new.fetch(['value1']) is None
    assert new.value1 == 3
