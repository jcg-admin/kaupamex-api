"""``BaseModel._read_grouping_sets`` — varios agrupados en una consulta.

≙ ``odoo19c: odoo/orm/models.py:1598-1859``. Diseño en
``designs/read-grouping-sets.md`` del Workbench.

*Métrica:* las listas por conjunto sobre registros sembrados.
*Ciega a:* las propiedades (unidad 6e) y el plan de consulta.
"""
import pytest

from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db


@pytest.fixture
def env(db):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment


@pytest.fixture
def data(env):
    first = env['test_orm.discussion'].create({'name': 'first'})
    second = env['test_orm.discussion'].create({'name': 'second'})
    messages = env['test_orm.message'].create([
        {'discussion': first.id, 'priority': 1, 'name': 'a'},
        {'discussion': first.id, 'priority': 4, 'name': 'b'},
        {'discussion': second.id, 'priority': 10, 'name': 'c'},
    ])
    return first, second, messages


@pytest.fixture
def tagged(env):
    red, blue = env['test_orm.category'].create(
        [{'name': 'red'}, {'name': 'blue'}])
    one = env['test_orm.discussion'].create(
        {'name': 'one', 'categories': [(6, 0, [red.id, blue.id])]})
    two = env['test_orm.discussion'].create(
        {'name': 'two', 'categories': [(6, 0, [red.id])]})
    return red, blue, one | two


def _mine(records):
    return [('id', 'in', records.ids)]


def _ids(rows):
    return [tuple(value.id if hasattr(value, '_ids') else value
                  for value in row) for row in rows]


def test_three_grouping_sets_in_one_call(env, data):
    first, second, messages = data
    model = env['test_orm.message']
    by_discussion, by_both, total = model._read_grouping_sets(
        _mine(messages), [['discussion'], ['discussion', 'priority'], []],
        ['__count', 'priority:sum'], order='discussion, priority')
    assert _ids(by_discussion) == [(first.id, 2, 5), (second.id, 1, 10)]
    assert _ids(by_both) == [(first.id, 1, 1, 1), (first.id, 4, 1, 4),
                             (second.id, 10, 1, 10)]
    assert total == [(3, 15)]


def test_sets_on_the_same_columns_share_their_result(env, data):
    first, second, messages = data
    left, right = env['test_orm.message']._read_grouping_sets(
        _mine(messages), [['discussion'], ['discussion']], ['__count'],
        order='discussion')
    assert _ids(left) == _ids(right) == [(first.id, 2), (second.id, 1)]
    assert left is not right


def test_empty_grouping_sets_are_rejected(env):
    with pytest.raises(ValueError, match='cannot be empty'):
        env['test_orm.message']._read_grouping_sets([], [], ['__count'])


def test_an_empty_domain_gives_one_empty_list_per_set(env):
    assert env['test_orm.message']._read_grouping_sets(
        [('id', 'in', [])], [['discussion'], []], ['__count']) == [[], []]


def test_a_many2many_count_is_distinct_by_record(env, tagged):
    red, blue, discussions = tagged
    by_category, total = env['test_orm.discussion']._read_grouping_sets(
        _mine(discussions), [['categories'], []], ['__count'],
        order='categories')
    assert sorted(_ids(by_category)) == sorted(
        [(red.id, 2), (blue.id, 1)])
    assert total == [(2,)]


def test_a_sensitive_aggregate_over_many2many_is_decomposed(env, tagged):
    red, blue, discussions = tagged
    one, two = discussions
    by_category, total = env['test_orm.discussion']._read_grouping_sets(
        _mine(discussions), [['categories'], []], ['id:sum'])
    assert sorted(_ids(by_category)) == sorted(
        [(red.id, one.id + two.id), (blue.id, one.id)])
    assert total == [(one.id + two.id,)]
