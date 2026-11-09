"""``_read_group_expand_full`` y ``_read_group_fill_results``.

≙ ``odoo19c: odoo/orm/models.py:2310-2385`` y ``Selection._get_attrs``
(``odoo19c: odoo/orm/fields_selection.py:85-91``). Diseño en
``designs/read-group-fill-results.md`` del Workbench.

*Métrica:* las listas de dicts devueltas sobre filas sembradas.
*Ciega a:* ``read_group``/``formatted_read_group`` (unidad 6b).
"""
import pytest

from orm.environments import Environment
from orm.fields_selection import SelectionField
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db

AGGREGATES = {'__count': '__count', 'priority:sum': 'priority:sum'}


@pytest.fixture
def env(db):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment


@pytest.fixture
def discussions(env):
    return env['test_orm.discussion'].create(
        [{'name': 'first'}, {'name': 'second'}, {'name': 'third'}])


def _model(env):
    return env['test_orm.message']._from_ids(env, (), ())


def _field(env, name):
    return env['test_orm.message']._fields[name]


def _line(discussion, count, total):
    return {'discussion': discussion, '__count': count,
            'priority:sum': total}


def test_without_group_expand_the_result_is_returned_unchanged(
        env, discussions):
    result = [_line(discussions[:1], 2, 5)]
    assert _model(env)._read_group_fill_results(
        [], 'discussion', AGGREGATES, result) is result


def test_a_callable_expands_a_many2one_to_its_universe(
        env, discussions, monkeypatch):
    monkeypatch.setattr(_field(env, 'discussion'), 'group_expand',
                        lambda model, groups, domain: discussions)
    second = discussions[1:2]
    rows = _model(env)._read_group_fill_results(
        [], 'discussion', AGGREGATES, [_line(second, 1, 10)])
    assert [(row['discussion'].id, row['__count'], row['priority:sum'])
            for row in rows] == [(discussions[0].id, 0, False),
                                 (second.id, 1, 10),
                                 (discussions[2].id, 0, False)]


def test_a_method_name_is_looked_up_on_the_model(
        env, discussions, monkeypatch):
    model_class = type(_model(env))
    monkeypatch.setattr(model_class, '_expand_all_discussions',
                        lambda self, groups, domain: discussions,
                        raising=False)
    monkeypatch.setattr(_field(env, 'discussion'), 'group_expand',
                        '_expand_all_discussions')
    rows = _model(env)._read_group_fill_results(
        [], 'discussion', AGGREGATES, [])
    assert [row['discussion'].id for row in rows] == discussions.ids


def test_a_group_outside_the_universe_goes_last(
        env, discussions, monkeypatch):
    monkeypatch.setattr(_field(env, 'discussion'), 'group_expand',
                        lambda model, groups, domain: discussions[1:])
    first = discussions[:1]
    rows = _model(env)._read_group_fill_results(
        [], 'discussion', AGGREGATES, [_line(first, 3, 1)])
    assert [row['discussion'].id for row in rows] == [
        discussions[1].id, discussions[2].id, first.id]


def test_a_scalar_universe_is_reversed_for_a_descending_order(
        env, monkeypatch):
    monkeypatch.setattr(_field(env, 'priority'), 'group_expand',
                        lambda model, values, domain: [1, 4, 10])
    rows = _model(env)._read_group_fill_results(
        [], 'priority', {'__count': '__count'},
        [{'priority': 4, '__count': 2}], read_group_order='priority desc')
    assert [(row['priority'], row['__count']) for row in rows] == [
        (10, 0), (4, 2), (1, 0)]


def test_the_fold_value_is_read_from_the_comodel(
        env, discussions, monkeypatch):
    monkeypatch.setattr(type(discussions), '_fold_name', 'name')
    monkeypatch.setattr(_field(env, 'discussion'), 'group_expand',
                        lambda model, groups, domain: discussions[:2])
    rows = _model(env)._read_group_fill_results(
        [], 'discussion', AGGREGATES, [])
    assert [row['__fold'] for row in rows] == ['first', 'second']


def test_expand_full_returns_every_record_of_the_comodel(env, discussions):
    groups = discussions[:1]
    expanded = _model(env)._read_group_expand_full(groups, [])
    assert set(discussions.ids) <= set(expanded.ids)
    assert expanded.ids == env['test_orm.discussion'].search([]).ids


def test_selection_group_expand_true_resolves_to_the_default_expander():
    field = SelectionField([('a', 'A'), ('b', 'B')], group_expand=True)
    attrs = field._get_attrs(type('Probe', (), {'_name': 'x.probe'}), 'state')
    assert attrs['group_expand'] == field._default_group_expand
