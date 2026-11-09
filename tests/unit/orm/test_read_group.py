"""``BaseModel._read_group`` — agrupado y agregados en una consulta.

≙ ``odoo19c: odoo/orm/models.py:1861-1952``. Diseño en
``designs/read-group.md`` del Workbench.

*Métrica:* las tuplas devueltas sobre filas sembradas.
*Ciega a:* ``read_group``/``formatted_read_group`` (unidad 6).
"""
import pytest

from addons.base.models.ir_model import IrModel, IrModelAccess
from addons.base.models.ir_rule import IrRule
from orm.environments import Environment
from orm.utils import SUPERUSER_ID
from tests.factories.user_factory import UserFactory

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


def _mine(messages):
    return [('id', 'in', messages.ids)]


def test_it_groups_by_a_many2one_with_aggregates(env, data):
    first, second, messages = data
    rows = env['test_orm.message']._read_group(
        _mine(messages), ['discussion'], ['__count', 'priority:sum'],
        order='discussion')
    assert [(d.id, count, total) for d, count, total in rows] == [
        (first.id, 2, 5), (second.id, 1, 10)]
    assert rows[0][0]._name == 'test_orm.discussion'


def test_having_filters_groups(env, data):
    first, _second, messages = data
    rows = env['test_orm.message']._read_group(
        _mine(messages), ['discussion'], ['__count'],
        having=[('__count', '>', 1)])
    assert [(d.id, count) for d, count in rows] == [(first.id, 2)]


def test_order_by_an_aggregate(env, data):
    first, second, messages = data
    rows = env['test_orm.message']._read_group(
        _mine(messages), ['discussion'], ['priority:sum'],
        order='priority:sum desc')
    assert [d.id for d, _total in rows] == [second.id, first.id]


def test_without_groupby_there_is_one_row(env, data):
    _first, _second, messages = data
    assert env['test_orm.message']._read_group(
        _mine(messages), [], ['__count', 'priority:max']) == [(3, 10)]


def test_an_empty_domain_without_groupby_gives_the_empty_values(env):
    assert env['test_orm.message']._read_group(
        [('id', 'in', [])], [], ['__count', 'priority:sum']) == [(0, False)]


def test_an_empty_domain_with_groupby_gives_nothing(env):
    assert env['test_orm.message']._read_group(
        [('id', 'in', [])], ['discussion'], ['__count']) == []


def test_a_rule_hides_the_groups_of_forbidden_rows(env, data):
    first, _second, messages = data
    label = env['test_orm.message']._meta.label
    row, _ = IrModel.objects.get_or_create(
        model=label, defaults={'name': 'test_orm.message'})
    IrModelAccess.objects.create(name='read message', model_id=row,
                                 perm_read=True)
    IrRule.objects.create(name='low priority', model_name=label,
                          domain_force="[('priority', '<', 5)]")
    with Environment(None, UserFactory().pk, {}) as plain:
        rows = plain['test_orm.message']._read_group(
            _mine(messages), ['discussion'], ['__count'])
    assert [(d.id, count) for d, count in rows] == [(first.id, 2)]
