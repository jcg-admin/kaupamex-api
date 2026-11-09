"""``BaseModel._read_group_groupby`` — la expresión SQL de un agrupado.

≙ ``odoo19c: odoo/orm/models.py:2015-2119``. Diseño en
``designs/read-group-groupby.md`` del Workbench.

*Métrica:* el ``SQL`` (código y parámetros) y las uniones del ``Query``.
*Ciega a:* la ejecución, que corresponde a ``_read_group`` (unidad 5).
"""
import pytest

from orm.environments import Environment
from orm.utils import SUPERUSER_ID
from tools.misc import get_lang
from tools.query import Query

pytestmark = pytest.mark.django_db


@pytest.fixture
def env(db):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment


def _query(model):
    return Query(model.env, model._table, model._table_sql)


def _code(sql):
    return ' '.join(sql.code.split())


def _groupby(model, spec):
    query = _query(model)
    return model._read_group_groupby(model._table, spec, query), query


def test_a_plain_field_is_its_column(env):
    sql, _ = _groupby(env['test_orm.message'].browse(()), 'priority')
    assert _code(sql) == '"test_orm_message"."priority"'


def test_a_boolean_groups_nulls_as_false(env):
    sql, _ = _groupby(env['test_orm.message'].browse(()), 'important')
    assert _code(sql) == 'COALESCE("test_orm_message"."important", FALSE)'


@pytest.mark.parametrize('model, spec, message', [
    ('test_orm.message', 'nope', "Invalid field 'nope'"),
    ('test_orm.message', 'priority:month',
     'Granularity set on a no-datetime field'),
    ('test_orm.mixed', 'date', 'Granularity not set on a date'),
    ('test_orm.mixed', 'date:bogus', "Granularity specification isn't"),
    ('test_orm.message', 'priority.name', 'Only many2one path is accepted'),
])
def test_invalid_specs_are_rejected(env, model, spec, message):
    with pytest.raises(ValueError, match=message):
        _groupby(env[model].browse(()), spec)


def test_a_date_truncates_and_comes_back_as_date(env):
    sql, _ = _groupby(env['test_orm.mixed'].browse(()), 'date:month')
    assert _code(sql) == \
        'date_trunc(%s, "test_orm_mixed"."date"::timestamp)::date'
    assert sql.params == ['month']


def test_a_number_granularity_is_a_date_part(env):
    sql, _ = _groupby(env['test_orm.mixed'].browse(()), 'date:year_number')
    assert _code(sql) == 'date_part(%s, "test_orm_mixed"."date")'
    assert sql.params == ['year']


def test_a_week_shifts_by_the_first_day_of_the_language(env):
    mixed = env['test_orm.mixed'].browse(())
    sql, _ = _groupby(mixed, 'date:week')
    first_week_day = int(get_lang(env).week_start) - 1
    days_offset = first_week_day and 7 - first_week_day
    interval = f"-{days_offset} DAY"
    assert _code(sql) == (
        "(date_trunc('week', \"test_orm_mixed\".\"date\"::timestamp"
        " - INTERVAL %s) + INTERVAL %s)::date")
    assert sql.params == [interval, interval]


def test_a_datetime_without_tz_truncates_in_utc(env):
    sql, _ = _groupby(env['test_orm.message'].browse(()), 'created_at:day')
    assert _code(sql) == \
        'date_trunc(%s, "test_orm_message"."created_at"::timestamp)'


def test_the_zone_comes_from_the_recordset_context(env):
    """La fuente lee ``model.env.context['tz']``; un recordset con otra zona
    que la del entorno activo agrupa con la suya."""
    message = env['test_orm.message'].browse(()).with_context(
        tz='America/Mexico_City')
    sql, _ = _groupby(message, 'created_at:hour_number')
    assert _code(sql) == ("date_part(%s, timezone(%s, timezone('UTC', "
                          "\"test_orm_message\".\"created_at\")))")
    assert sql.params == ['hour', 'America/Mexico_City']


def test_a_many2one_path_joins_the_comodel(env):
    sql, query = _groupby(env['test_orm.message'].browse(()),
                          'discussion.name')
    assert _code(sql) == '"test_orm_message__discussion"."name"'
    joins = ' '.join(query.from_clause.code.split())
    assert 'LEFT JOIN "test_orm_discussion" AS "test_orm_message__discussion"'\
        ' ON ("test_orm_message"."discussion" =' \
        ' "test_orm_message__discussion"."id")' in joins


def test_a_many2many_joins_its_relation_table(env):
    sql, query = _groupby(env['test_orm.discussion'].browse(()),
                          'categories')
    assert _code(sql) == '"test_orm_discussion__categories"."category"'
    joins = ' '.join(query.from_clause.code.split())
    assert 'LEFT JOIN "test_orm_discussion_category" AS' \
        ' "test_orm_discussion__categories" ON ("test_orm_discussion"."id" =' \
        ' "test_orm_discussion__categories"."discussion")' in joins
