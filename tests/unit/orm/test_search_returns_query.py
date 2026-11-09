"""``BaseModel._search`` devuelve el ``Query`` de la referencia.

≙ ``odoo19c: odoo/orm/models.py:5324-5394`` y sus consumidores
``search_count``/``search``/``search_fetch`` (``:1347-1428``). Diseño en
``designs/search-returns-query.md`` del Workbench; evidencia previa en
``designs/search-contract-analysis.md``.

*Métrica:* el tipo devuelto, sus cláusulas, las filas y el número de
consultas.
*Ciega a:* el coste en tablas grandes; el plan se midió en el análisis.
"""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from addons.base.models.ir_model import IrModel, IrModelAccess
from addons.base.models.ir_rule import IrRule
from exceptions import AccessError
from orm.environments import Environment
from orm.utils import SUPERUSER_ID
from tests.factories.user_factory import UserFactory
from tools.query import Query

pytestmark = pytest.mark.django_db


@pytest.fixture
def env(db):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment


def _grant(env, model_name):
    label = env[model_name]._meta.label
    row, _ = IrModel.objects.get_or_create(
        model=label, defaults={'name': model_name})
    IrModelAccess.objects.create(name=f'read {model_name}', model_id=row,
                                 perm_read=True)
    return label


def _model(environment, name):
    return type(environment[name].browse(()))


@pytest.fixture
def foos(env):
    return env['test_orm.foo'].create(
        [{'value1': 1, 'name': 'a'}, {'value1': 2, 'name': ''},
         {'value1': 3}])


def test_it_returns_an_unexecuted_query(env, foos):
    Foo = _model(env, 'test_orm.foo')
    with CaptureQueriesContext(connection) as captured:
        query = Foo._search([('value1', '>', 1)])
    assert isinstance(query, Query)
    assert len(captured.captured_queries) == 0
    assert set(query) & set(foos.ids) == {foos[1].id, foos[2].id}


def test_a_false_domain_is_an_empty_query(env):
    Foo = _model(env, 'test_orm.foo')
    assert Foo._search([('id', 'in', [])]).is_empty()


def test_active_test_filters_archived_unless_asked(env):
    Model = _model(env, 'test_orm.model_active_field')
    kept = env['test_orm.model_active_field'].create({'name': 'k'})
    gone = env['test_orm.model_active_field'].create(
        {'name': 'g', 'active': False})
    mine = {kept.id, gone.id}
    assert set(Model._search([])) & mine == {kept.id}
    assert set(Model._search([('active', 'in', [True, False])])) & mine \
        == mine
    assert set(Model._search([], active_test=False)) & mine == mine
    with Environment(None, SUPERUSER_ID, {'active_test': False}) as off:
        assert set(_model(off, 'test_orm.model_active_field')._search([])) \
            & mine == mine


def test_the_rule_goes_into_the_where_of_one_query(env, foos):
    label = _grant(env, 'test_orm.foo')
    IrRule.objects.create(name='two up', model_name=label,
                          domain_force="[('value1', '>=', 2)]")
    with Environment(None, UserFactory().pk, {}) as plain:
        Foo = _model(plain, 'test_orm.foo')
        query = Foo._search([])
        with CaptureQueriesContext(connection) as captured:
            ids = set(query)
        assert ids & set(foos.ids) == {foos[1].id, foos[2].id}
        assert len(captured.captured_queries) == 1


def test_bypass_access_skips_the_rules(env, foos):
    label = _grant(env, 'test_orm.foo')
    IrRule.objects.create(name='none', model_name=label,
                          domain_force="[('value1', '=', 99)]")
    with Environment(None, UserFactory().pk, {}) as plain:
        Foo = _model(plain, 'test_orm.foo')
        assert not set(Foo._search([])) & set(foos.ids)
        assert set(Foo._search([], bypass_access=True)) >= set(foos.ids)


def test_without_read_access_it_raises(env):
    with Environment(None, UserFactory().pk, {}) as plain:
        with pytest.raises(AccessError):
            _model(plain, 'test_orm.foo')._search([])


def test_order_limit_and_offset_are_set_on_the_query(env, foos):
    Foo = _model(env, 'test_orm.foo')
    query = Foo._search([('id', 'in', foos.ids)], offset=1, limit=1,
                        order='value1 desc')
    assert query.limit == 1 and query.offset == 1
    assert list(query) == [foos[1].id]
    assert Foo._search([], limit=False).limit is None


def test_the_query_is_a_domain_value(env, foos):
    Foo = _model(env, 'test_orm.foo')
    query = Foo._search([('value1', '=', 3)])
    found = env['test_orm.foo'].search([('id', 'in', query)])
    assert found.ids == [foos[2].id]


def test_search_count_counts_the_query(env, foos):
    Foo = _model(env, 'test_orm.foo')
    assert Foo.search_count([('id', 'in', foos.ids),
                             ('value1', '>=', 2)]) == 2


def test_an_ordered_comparison_converts_its_value(env, foos):
    """``_to_sql`` convierte el valor con el campo; el filtro de Django
    comparaba un entero con una cadena y lanzaba ``TypeError``
    (``outputs/search-contract/grid-basemodel.json``)."""
    found = env['test_orm.foo'].search([('id', 'in', foos.ids),
                                        ('value1', '>=', '3')])
    assert found.ids == [foos[2].id]
