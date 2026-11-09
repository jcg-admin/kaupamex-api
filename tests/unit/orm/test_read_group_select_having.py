"""``BaseModel._read_group_select`` y ``_read_group_having``.

≙ ``odoo19c: odoo/orm/models.py:1953-2013`` y ``:2121-2148``, con
``READ_GROUP_AGGREGATE`` (``:300-313``). Diseño en
``designs/read-group-family-plan.md`` (unidad 1) del Workbench.

*Métrica:* el ``SQL.code`` del agregado o del ``HAVING`` y las uniones de
``Query``.
*Ciega a:* la ejecución, que corresponde a ``_read_group`` (unidad 5).
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import ResCompany
from orm.environments import company_scope
from orm.environments import env as current_env
from orm.environments import sudo, user_scope
from tools.query import Query

pytestmark = pytest.mark.django_db


@pytest.fixture
def environment():
    user = get_user_model().objects.create_user(
        login='read-group-select', password=None, name='u')
    with user_scope(user.pk), sudo():
        yield current_env()


def _model(environment, name):
    return environment[name].browse(())


def _query(model):
    return Query(model.env, model._table, model._table_sql)


def _code(sql):
    return ' '.join(sql.code.split())


@pytest.mark.parametrize('spec, expected', [
    ('__count', 'COUNT(*)'),
    ('priority:sum', 'SUM("test_orm_message"."priority")'),
    ('priority:avg', 'AVG("test_orm_message"."priority")'),
    ('priority:max', 'MAX("test_orm_message"."priority")'),
    ('priority:min', 'MIN("test_orm_message"."priority")'),
    ('important:bool_and', 'BOOL_AND("test_orm_message"."important")'),
    ('important:bool_or', 'BOOL_OR("test_orm_message"."important")'),
    ('priority:array_agg', 'ARRAY_AGG("test_orm_message"."priority"'
                           ' ORDER BY "test_orm_message"."id")'),
    ('priority:array_agg_distinct',
     'ARRAY_AGG(DISTINCT "test_orm_message"."priority"'
     ' ORDER BY "test_orm_message"."priority")'),
    ('discussion:recordset', 'ARRAY_AGG("test_orm_message"."discussion"'
                             ' ORDER BY "test_orm_message"."id")'),
    ('id:recordset', 'ARRAY_AGG("test_orm_message"."id"'
                     ' ORDER BY "test_orm_message"."id")'),
    ('priority:count', 'COUNT("test_orm_message"."priority")'),
    ('priority:count_distinct',
     'COUNT(DISTINCT "test_orm_message"."priority")'),
])
def test_each_aggregate_has_its_sql(environment, spec, expected):
    message = _model(environment, 'test_orm.message')
    assert _code(message._read_group_select(spec, _query(message))) == \
        expected


@pytest.mark.parametrize('spec, message', [
    ('priority', 'Aggregate method is mandatory'),
    ('nope:sum', "Invalid field 'nope'"),
    ('discussion.name:sum', 'dot notation is not supported'),
    ('priority:median', "Invalid aggregate method 'median'"),
    ('priority:recordset', 'can be only used on relational field'),
    ('priority:sum_currency', 'only works on currency field'),
])
def test_invalid_specs_are_rejected(environment, spec, message):
    model = _model(environment, 'test_orm.message')
    with pytest.raises(ValueError, match=message):
        model._read_group_select(spec, _query(model))


def test_sum_currency_joins_the_latest_rate(environment):
    company = ResCompany.objects.create(code='rg-sum', name='RG Sum')
    mixed = _model(environment, 'test_orm.mixed')
    query = _query(mixed)
    with company_scope(company.pk):
        code = _code(mixed._read_group_select('amount:sum_currency', query))
    assert code == ('SUM("test_orm_mixed"."amount" /'
                    ' COALESCE("test_orm_mixed__currency_id__rates"."rate",'
                    ' 1.0))')
    joins = ' '.join(query.from_clause.code.split())
    assert 'LEFT JOIN (SELECT DISTINCT ON' in joins
    assert company.root_id.id in query.from_clause.params
    assert 'WHERE "res_currency_rate"."company_id" IS NULL OR' \
        ' "res_currency_rate"."company_id" = %s' in joins
    assert 'AS "test_orm_mixed__currency_id__rates" ON' \
        ' ("test_orm_mixed"."currency_id" =' \
        ' "test_orm_mixed__currency_id__rates"."currency_id")' in joins


def test_an_empty_having_is_empty(environment):
    message = _model(environment, 'test_orm.message')
    assert message._read_group_having([], _query(message)).code == ''


def test_having_terms_are_and_by_default(environment):
    message = _model(environment, 'test_orm.message')
    sql = message._read_group_having(
        [('__count', '>', 2), ('priority:sum', '<=', 10)], _query(message))
    assert _code(sql) == \
        '(COUNT(*) > %s AND SUM("test_orm_message"."priority") <= %s)'
    assert sql.params == [2, 10]


def test_having_supports_prefix_operators(environment):
    message = _model(environment, 'test_orm.message')
    sql = message._read_group_having(
        ['|', ('__count', '=', 1), '!', ('priority:max', '>=', 5)],
        _query(message))
    assert _code(sql) == \
        '(COUNT(*) = %s OR (NOT MAX("test_orm_message"."priority") >= %s))'


@pytest.mark.parametrize('domain', [
    [('__count', 'like', 'x')],
    ['nope'],
])
def test_invalid_having_clauses_are_rejected(environment, domain):
    message = _model(environment, 'test_orm.message')
    with pytest.raises(ValueError, match='Invalid having clause'):
        message._read_group_having(domain, _query(message))
