"""``BaseModel._read_group_orderby`` — el ``ORDER BY`` de un agrupado.

≙ ``odoo19c: odoo/orm/models.py`` (``_read_group_orderby``) y
``regex_order_part_read_group`` (``:105-111``). Diseño en
``designs/read-group-orderby.md`` del Workbench.

*Métrica:* el ``SQL`` devuelto y los términos de agrupado que modifica.
*Ciega a:* la ejecución, que corresponde a ``_read_group`` (unidad 5).
"""
import pytest

from orm.environments import Environment
from orm.utils import SUPERUSER_ID
from tools.misc import get_lang
from tools.query import Query
from tools.sql import SQL

pytestmark = pytest.mark.django_db


@pytest.fixture
def env(db):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment


def _code(sql):
    return ' '.join(sql.code.split())


def _query(model):
    return Query(model.env, model._table, model._table_sql)


def test_nothing_to_order_gives_an_empty_sql(env):
    message = env['test_orm.message'].browse(())
    assert message._read_group_orderby('', {}, _query(message)).code == ''


def test_without_order_the_groupby_terms_order(env):
    message = env['test_orm.message'].browse(())
    query = _query(message)
    terms = {'priority': message._read_group_groupby(
        message._table, 'priority', query)}
    sql = message._read_group_orderby(None, terms, query)
    assert _code(sql) == '"test_orm_message"."priority" ASC'


def test_direction_and_nulls_are_kept(env):
    message = env['test_orm.message'].browse(())
    query = _query(message)
    terms = {'priority': SQL.identifier('test_orm_message', 'priority')}
    sql = message._read_group_orderby('priority desc nulls last', terms,
                                      query)
    assert _code(sql) == '"test_orm_message"."priority" DESC NULLS LAST'


def test_a_term_outside_the_groupby_orders_as_an_aggregate(env):
    message = env['test_orm.message'].browse(())
    query = _query(message)
    sql = message._read_group_orderby('priority:sum desc', {}, query)
    assert _code(sql) == 'SUM("test_orm_message"."priority") DESC'


@pytest.mark.parametrize('order, error', [
    ('priority sideways', 'Invalid order'),
    ('nope asc', 'is not a valid aggregate nor valid groupby'),
])
def test_invalid_orders_are_rejected(env, order, error):
    message = env['test_orm.message'].browse(())
    with pytest.raises(ValueError, match=error):
        message._read_group_orderby(order, {}, _query(message))


def test_day_of_week_shifts_by_the_first_day_of_the_language(env):
    message = env['test_orm.message'].browse(())
    query = _query(message)
    term = 'created_at:day_of_week'
    terms = {term: message._read_group_groupby(message._table, term, query)}
    sql = message._read_group_orderby(f'{term} asc', terms, query)
    assert _code(sql).startswith('mod(7 - %s + date_part(')
    assert _code(sql).endswith('::int, 7) ASC')
    assert sql.params[0] == int(get_lang(env).week_start)


def test_a_many2one_ordered_by_name_orders_by_the_comodel(env):
    category = env['test_orm.category'].browse(())
    query = _query(category)
    terms = {'parent': category._read_group_groupby(
        category._table, 'parent', query)}
    before = terms['parent']
    sql = category._read_group_orderby('parent asc', terms, query)
    assert '"name"' in sql.code
    assert '"test_orm_category__parent"' in query.from_clause.code
    assert terms['parent'] is not before
    assert '"name"' in terms['parent'].code
