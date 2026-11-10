"""``BaseModel.read_group`` — el agrupado formateado, obsoleto desde 19.0.

≙ ``odoo19c: odoo/orm/models.py:112`` (``regex_field_agg``) y
``:2746-2878``. Diseño en ``designs/read-group-public.md`` del Workbench.

*Métrica:* las filas devueltas sobre registros sembrados.
*Ciega a:* el agrupado por propiedades (unidad 6e) y
``formatted_read_group`` de ``web``.
"""
import datetime
import warnings

import pytest

from orm.environments import Environment
from orm.models import regex_field_agg
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db


@pytest.fixture
def env(db, system_user):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment


@pytest.fixture
def data(env):
    first = env['test_orm.discussion'].create(
        {'name': 'first', 'participants': [(6, 0, [env.user.id])]})
    second = env['test_orm.discussion'].create(
        {'name': 'second', 'participants': [(6, 0, [env.user.id])]})
    messages = env['test_orm.message'].create([
        {'discussion': first.id, 'priority': 1, 'name': 'a'},
        {'discussion': first.id, 'priority': 4, 'name': 'b'},
        {'discussion': second.id, 'priority': 10, 'name': 'c'},
    ])
    return first, second, messages


def _read_group(env, model, *args, **kwargs):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        return env[model]._from_ids(env, (), ()).read_group(*args, **kwargs)


def _mine(records):
    return [('id', 'in', records.ids)]


def test_lazy_by_many2one_counts_and_takes_the_default_aggregator(
        env, data):
    first, second, messages = data
    rows = _read_group(env, 'test_orm.message', _mine(messages),
                       ['priority'], ['discussion'])
    assert [(row['discussion'], row['discussion_count'], row['priority'])
            for row in rows] == [((first.id, 'first'), 2, 5),
                                 ((second.id, 'second'), 1, 10)]
    assert isinstance(rows[0]['__domain'], list)
    assert ('discussion', '=', first.id) in rows[0]['__domain']


def test_named_and_explicit_aggregates(env, data):
    first, second, messages = data
    rows = _read_group(env, 'test_orm.message', _mine(messages),
                       ['top:max(priority)', 'priority:min'], ['discussion'])
    assert [(row['top'], row['priority']) for row in rows] == [
        (4, 1), (10, 10)]


def test_eager_counts_all_and_lazy_carries_the_rest_in_context(env, data):
    _first, _second, messages = data
    eager = _read_group(env, 'test_orm.message', _mine(messages),
                        ['__count'], ['discussion', 'priority'], lazy=False)
    assert sorted(row['__count'] for row in eager) == [1, 1, 1]
    assert all('__context' not in row for row in eager)
    lazy = _read_group(env, 'test_orm.message', _mine(messages),
                       ['__count'], ['discussion', 'priority'])
    assert lazy[0]['__context'] == {'group_by': ['priority']}


def test_an_unknown_field_is_rejected(env, data):
    _first, _second, messages = data
    with pytest.raises(ValueError, match='Invalid field'):
        _read_group(env, 'test_orm.message', _mine(messages), ['__count'],
                    ['nonexistent'])


def test_orderby_is_rewritten_to_the_annotated_aggregate(env, data):
    first, second, messages = data
    rows = _read_group(env, 'test_orm.message', _mine(messages),
                       ['priority:sum'], ['discussion'],
                       orderby='priority desc')
    assert [row['discussion'][0] for row in rows] == [second.id, first.id]


def test_fill_temporal_in_context_fills_the_missing_months(env):
    records = env['test_orm.mixed'].create([
        {'date': datetime.date(2026, 6, 15)},
        {'date': datetime.date(2026, 9, 3)},
    ])
    model = env['test_orm.mixed']._from_ids(env, (), ()).with_context(
        fill_temporal=True)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        rows = model.read_group(_mine(records), ['__count'], ['date:month'])
    assert [(row['date:month'], row['date_count']) for row in rows] == [
        ('June 2026', 1), ('July 2026', 0), ('August 2026', 0),
        ('September 2026', 1)]


def test_it_warns_that_it_is_deprecated(env, data):
    _first, _second, messages = data
    model = env['test_orm.message']._from_ids(env, (), ())
    with pytest.warns(DeprecationWarning, match='read_group is deprecated'):
        model.read_group(_mine(messages), ['__count'], ['discussion'])


def test_the_field_aggregate_regex_matches_the_three_forms():
    assert regex_field_agg.match('priority').groups() == (
        'priority', None, None)
    assert regex_field_agg.match('priority:sum').groups() == (
        'priority', 'sum', None)
    assert regex_field_agg.match('top:max(priority)').groups() == (
        'top', 'max', 'priority')
