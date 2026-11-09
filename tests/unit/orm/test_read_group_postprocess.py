"""Valor vacío y posproceso de ``_read_group``.

≙ ``_read_group_empty_value``, ``_read_group_postprocess_groupby`` y
``_read_group_postprocess_aggregate`` (``odoo19c: odoo/orm/models.py``).
Diseño en ``designs/read-group-postprocess.md`` del Workbench.

*Métrica:* el valor que cada función devuelve para un spec y unos valores
crudos.
*Ciega a:* la consulta que produce esos valores, que es de ``_read_group``.
"""
import pytest
from django.contrib.auth import get_user_model

from orm.environments import env as current_env
from orm.environments import sudo, user_scope

pytestmark = pytest.mark.django_db


@pytest.fixture
def message():
    user = get_user_model().objects.create_user(
        login='read-group-post', password=None, name='u')
    with user_scope(user.pk), sudo():
        yield current_env()['test_orm.message'].browse(())


@pytest.mark.parametrize('spec, expected', [
    ('__count', 0),
    ('priority:count', 0),
    ('priority:count_distinct', 0),
    ('priority:array_agg', []),
    ('priority:array_agg_distinct', []),
    ('priority:sum', False),
    ('name', False),
])
def test_scalar_empty_values(message, spec, expected):
    assert message._read_group_empty_value(spec) == expected


@pytest.mark.parametrize('spec, model', [
    ('discussion', 'test_orm.discussion'),
    ('discussion:recordset', 'test_orm.discussion'),
    ('id:recordset', 'test_orm.message'),
])
def test_relational_empty_value_is_the_empty_recordset(message, spec, model):
    value = message._read_group_empty_value(spec)
    assert value._name == model
    assert not value


def test_a_django_comodel_gives_its_empty_rows(message):
    value = message._read_group_empty_value('author')
    assert value.model is get_user_model()
    assert not value


def test_a_many2one_chain_asks_the_comodel(message):
    assert message._read_group_empty_value('discussion.name') is False
    moderator = message._read_group_empty_value('discussion.moderator')
    assert moderator.model is get_user_model() and not moderator


def test_groupby_values_become_singletons_sharing_the_prefetch(message):
    values = list(message._read_group_postprocess_groupby(
        'discussion', [7, None, 9]))
    assert [v._ids for v in values] == [(7,), (), (9,)]
    assert values[0]._prefetch_ids == (7, 9)
    assert values[1]._name == 'test_orm.discussion'


def test_scalar_groupby_nulls_become_the_empty_value(message):
    assert list(message._read_group_postprocess_groupby(
        'priority', [3, None])) == [3, False]


def test_recordset_aggregate_drops_repeats_and_nulls(message):
    values = list(message._read_group_postprocess_aggregate(
        'discussion:recordset', [[5, None, 5, 6], None, [6, 8]]))
    assert [v._ids for v in values] == [(5, 6), (), (6, 8)]
    assert values[0]._prefetch_ids == (5, 6, 8)


def test_count_nulls_become_zero(message):
    assert list(message._read_group_postprocess_aggregate(
        '__count', [4, None])) == [4, 0]
    assert list(message._read_group_postprocess_aggregate(
        'priority:sum', [None, 2])) == [False, 2]
