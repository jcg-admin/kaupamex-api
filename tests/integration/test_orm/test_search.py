"""``search`` sobre un recordset de ``BaseModel`` — ≙ ``odoo19c:
odoo/orm/models.py:1363`` (``search``) y ``:5324`` (``_search``).

Casos propios del Consumer para las ramas que ``test_sort`` no ejerce: el
filtro de archivados (``active_test``), su anulación por dominio y por
contexto, la ventana ``offset``/``limit`` y ``search_count``.
"""

import pytest

from orm.environments import context_scope

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def records(env):
    rows = env['test_orm.model_active_field'].create(
        [{'name': name} for name in ('a', 'b', 'c')])
    rows[1].active = False
    env.flush_all()
    return rows


def test_archived_records_are_left_out_by_default(env, records):
    found = env['test_orm.model_active_field'].search(
        [('id', 'in', records.ids)], order='name')
    assert found.mapped('name') == ['a', 'c']


def test_naming_active_in_the_domain_lifts_the_filter(env, records):
    found = env['test_orm.model_active_field'].search(
        [('id', 'in', records.ids), ('active', '=', False)])
    assert found.mapped('name') == ['b']


def test_the_context_lifts_the_filter(env, records):
    with context_scope(active_test=False):
        found = env['test_orm.model_active_field'].search(
            [('id', 'in', records.ids)], order='name')
    assert found.mapped('name') == ['a', 'b', 'c']


def test_offset_limit_and_count(env, records):
    Model = env['test_orm.model_active_field']
    domain = [('id', 'in', records.ids)]
    assert Model.search(domain, order='name', offset=1, limit=1).mapped(
        'name') == ['c']
    assert Model.search_count(domain) == 2


def test_hierarchy(env):
    """≙ ``TestSubqueries.test_hierarchy`` (``tests/test_search.py:385``).

    La fuente afirma tres consultas: dos para resolver la jerarquía y una
    para la búsqueda. Aquí se afirman las filas.
    """
    Head, Node = env['test_orm.hierarchy.head'], env['test_orm.hierarchy.node']
    parent_node = Node.create({})
    nodes = Node.create([{'parent_id': parent_node.id} for _ in range(3)])
    head = Head.create({'node_id': parent_node.id})
    other = Head.create({'node_id': Node.create({}).id})

    found = Head.search([('node_id', 'child_of', parent_node.ids)])
    assert found.ids == [head.id]
    found = Head.search([('node_id', 'parent_of', nodes.ids)])
    assert found.ids == [head.id]
    assert other.id not in Head.search(
        [('node_id', 'child_of', nodes.ids)]).ids
    # Caso propio del Consumer: una cabeza sobre un hijo sólo la alcanza
    # ``child_of`` si desciende; la de la fuente apunta al propio padre.
    on_child = Head.create({'node_id': nodes[0].id})
    found = Head.search([('node_id', 'child_of', parent_node.ids)])
    assert set(found.ids) == {head.id, on_child.id}


# ---------------------------------------------------------------------------
# ``TestSearchRelated.test_related_null`` (``tests/test_search.py:1046``). La
# fuente afirma el SQL de cada operador; aquí cada operador se compara contra
# el valor efectivo del ``related``: sin ``foo`` o con nombre nulo, el valor
# es ``False``, y un Char nulo es ``False`` en la fuente.
# ---------------------------------------------------------------------------


@pytest.fixture
def related_rows(env):
    Foo, Related = env['test_orm.related_foo'], env['test_orm.related']
    rows = {
        'no_foo': Related.create({'name': 'no_foo'}),
        'null_name': Related.create(
            {'name': 'null_name', 'foo_id': Foo.create({}).id}),
        'a': Related.create(
            {'name': 'a', 'foo_id': Foo.create({'name': 'a'}).id}),
        'b': Related.create(
            {'name': 'b', 'foo_id': Foo.create({'name': 'b'}).id}),
    }
    values = {'no_foo': False, 'null_name': False, 'a': 'a', 'b': 'b'}
    return rows, values


_PREDICATES = {
    '=': lambda v, x: v == x,
    '!=': lambda v, x: v != x,
    'in': lambda v, x: v in x,
    'not in': lambda v, x: v not in x,
}


@pytest.mark.parametrize('fname', ['foo_name', 'foo_name_sudo'])
@pytest.mark.parametrize(('operator', 'value'), [
    ('=', 'a'), ('!=', 'a'), ('=', False), ('!=', False),
    ('in', ['a', 'b']), ('not in', ['a', 'b']),
    ('in', ['a', False]), ('not in', ['a', False]),
])
def test_related_null(env, related_rows, fname, operator, value):
    rows, values = related_rows
    expected = {rows[key].id for key, current in values.items()
                if _PREDICATES[operator](current, value)}
    ids = {row.id for row in rows.values()}
    found = set(env['test_orm.related'].search([(fname, operator, value)]).ids)
    assert found & ids == expected
