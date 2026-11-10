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
from addons.base.models.res_groups import ResGroups
from exceptions import AccessError
from orm.environments import Environment
from orm.utils import SUPERUSER_ID
from tests.factories.user_factory import UserFactory
from tools.query import Query

pytestmark = pytest.mark.django_db


@pytest.fixture
def env(db, system_user):
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


# === Seguridad: nada que antes estuviera prohibido queda visible ==========


def _rule(label, domain, groups=()):
    rule = IrRule.objects.create(name=f'rule {domain}', model_name=label,
                                 domain_force=domain)
    if groups:
        rule.groups.set(groups)
    return rule


def test_an_or_in_the_domain_does_not_escape_the_rule(env, foos):
    _rule(_grant(env, 'test_orm.foo'), "[('value1', '>=', 2)]")
    with Environment(None, UserFactory().pk, {}) as plain:
        Foo = _model(plain, 'test_orm.foo')
        found = set(Foo._search(['|', ('value1', '=', 1),
                                 ('value1', '=', 3)]))
        assert found & set(foos.ids) == {foos[2].id}


def test_a_false_rule_gives_an_empty_query(env, foos):
    _rule(_grant(env, 'test_orm.foo'), "[(0, '=', 1)]")
    with Environment(None, UserFactory().pk, {}) as plain:
        query = _model(plain, 'test_orm.foo')._search([])
        assert query.is_empty() or not set(query) & set(foos.ids)


def test_global_and_group_rules_combine_like_the_reference(env, foos):
    """La global con ``AND``; de las de grupo sólo cuenta la del grupo del
    usuario (``odoo19c: ir_rule.py:158-173``)."""
    label = _grant(env, 'test_orm.foo')
    mine = ResGroups.objects.create(name='mine')
    other = ResGroups.objects.create(name='other')
    _rule(label, "[('value1', '>=', 2)]")
    _rule(label, "[('value1', '=', 2)]", groups=[mine])
    _rule(label, "[('value1', '=', 3)]", groups=[other])
    user = UserFactory()
    user.group_ids.add(mine)
    with Environment(None, user.pk, {}) as plain:
        assert mine.pk in set(plain.user._get_group_ids())
        found = set(_model(plain, 'test_orm.foo')._search([]))
        assert found & set(foos.ids) == {foos[1].id}


def test_the_comodel_rule_restricts_the_many2one_subquery(env):
    hidden = env['test_orm.discussion'].create(
        {'name': 'hidden', 'participants': [(6, 0, [env.user.id])]})
    shown = env['test_orm.discussion'].create(
        {'name': 'shown', 'participants': [(6, 0, [env.user.id])]})
    for discussion in (hidden, shown):
        env['test_orm.message'].create({'discussion': discussion.id,
                                        'name': 'm'})
    _grant(env, 'test_orm.message')
    _rule(_grant(env, 'test_orm.discussion'), "[('name', '!=', 'hidden')]")
    with Environment(None, UserFactory().pk, {}) as plain:
        Message = _model(plain, 'test_orm.message')
        found = Message.search([('discussion.name', 'in',
                                 ['hidden', 'shown'])])
        assert {m.discussion.id for m in found} <= {shown.id}


def test_a_restricted_query_stays_restricted_as_a_domain_value(env, foos):
    _rule(_grant(env, 'test_orm.foo'), "[('value1', '>=', 2)]")
    with Environment(None, UserFactory().pk, {}) as plain:
        query = _model(plain, 'test_orm.foo')._search([])
    found = env['test_orm.foo'].search([('id', 'in', query)])
    assert set(found.ids) & set(foos.ids) == {foos[1].id, foos[2].id}


def test_the_superuser_sees_every_record(env, foos):
    _rule(_grant(env, 'test_orm.foo'), "[(0, '=', 1)]")
    assert set(_model(env, 'test_orm.foo')._search([])) >= set(foos.ids)


def test_values_travel_as_parameters(env, foos):
    hostile = "a'); DROP TABLE test_orm_foo; --"
    query = _model(env, 'test_orm.foo')._search([('name', '=', hostile)])
    select = query.select()
    flat = [item for param in select.params
            for item in (param if isinstance(param, (list, tuple))
                         else [param])]
    assert hostile not in select.code
    assert hostile in flat
    assert not set(query) & set(foos.ids)


def test_a_django_comodel_rule_restricts_the_subquery(env):
    """``res.partner`` es un modelo de Django: su regla entra por
    ``fields_relational.django_comodel_rows`` y tiene que seguir acotando la
    subconsulta del many2one."""
    Partner = env['res.partner']
    hidden = Partner.objects.create(name='hidden-partner')
    shown = Partner.objects.create(name='shown-partner')
    for partner in (hidden, shown):
        env['test_orm.multi'].create({'partner': partner.id})
    _grant(env, 'test_orm.multi')
    _rule(_grant(env, 'res.partner'), "[('name', '!=', 'hidden-partner')]")
    with Environment(None, UserFactory().pk, {}) as plain:
        Multi = _model(plain, 'test_orm.multi')
        found = set(Multi._search([('partner.name', 'in',
                                    ['hidden-partner', 'shown-partner'])]))
    owners = {m.partner.id: m.id for m in env['test_orm.multi'].search(
        [('partner', 'in', [hidden.id, shown.id])])}
    assert found == {owners[shown.id]}
