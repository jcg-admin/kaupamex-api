"""Porte de ``odoo19c: odoo/addons/test_orm/tests/test_sort.py``.

Revisión de referencia: ``odoo-tools@abe4040ec1``. Cada caso compara el orden
de la base (``search(order=…)``) con el de ``recordset.sorted(…)``.

**Adaptaciones declaradas:** los contadores de consultas de la fuente
(``assertQueryCount``) no se portan aquí: miden prelectura, que es otro
contrato. ``test_sorted_new_id`` exige ``BaseModel.new`` y ``test_prefetch``
opera sobre ``res.partner``; ninguno de los dos existe aún como recordset de
``BaseModel`` (TASK-API-0397), y quedan fuera de este porte. En las lambdas
de Python el campo relacional se escribe ``country`` y no ``country_id``: el
árbol nombra así el campo y reserva ``country_id`` para la columna (las
cláusulas de orden aceptan los dos nombres).
"""

import pytest

from orm.identifiers import NewId

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def countries(env):
    return env['test_orm.country'].create([
        {'name': 'B'}, {'name': 'A'}, {'name': 'C'}])


@pytest.fixture
def cities(env, countries):
    b, a, c = countries
    return env['test_orm.city'].create([
        {'name': 'c2', 'country_id': c.id},
        {'name': 'b1', 'country_id': b.id},
        {'name': 'b2', 'country_id': b.id},
        {'name': 'c1', 'country_id': c.id},
        {'name': 'a1', 'country_id': a.id},
        {'name': 'a2', 'country_id': a.id},
    ])


def test_basic(env, countries):
    db_result = env['test_orm.country'].search([])
    assert db_result.ids == countries.sorted().ids
    assert db_result[::-1].ids == countries.sorted(reverse=True).ids
    assert countries.sorted().mapped('name') == ['A', 'B', 'C']


def test_stable(cities):
    assert (cities.sorted('name', reverse=True).sorted('country_id.id')
            == cities.sorted(lambda c: (-c.country.id, c.name), reverse=True))


def test_basic_m2o(env, cities):
    db_result = env['test_orm.city'].search([])
    assert db_result.ids == cities.sorted().ids
    assert db_result[::-1].ids == cities.sorted(reverse=True).ids
    assert cities.sorted().mapped('name') == ['a1', 'a2', 'b1', 'b2', 'c1', 'c2']


def test_basic_boolean(env):
    records = env['test_orm.model_active_field'].create(
        [{'name': v} for v in 'abc'])
    records[1].active = False
    t_records = records.filtered('active')
    f_records = records - t_records
    assert f_records + t_records == records.sorted('active, name')
    assert t_records + f_records == records.sorted('active DESC, name')


def test_custom_m2o(env, cities):
    order = 'country_id DESC, id ASC'
    db_result = env['test_orm.city'].search([], order=order)
    assert db_result.ids == cities.sorted(order).ids
    assert db_result[::-1].ids == cities.sorted(order, reverse=True).ids
    assert cities.sorted(order).mapped('name') == [
        'c2', 'c1', 'b1', 'b2', 'a1', 'a2']


@pytest.mark.parametrize('order', [
    'country_id ASC, id',
    'country_id DESC, id',
    'country_id ASC NULLS FIRST, id',
    'country_id DESC NULLS FIRST, id',
    'country_id ASC NULLS LAST, id',
    'country_id DESC NULLS LAST, id',
    'name ASC, id',
    'name DESC, id',
    'name ASC NULLS FIRST, id',
    'name DESC NULLS FIRST, id',
    'name ASC NULLS LAST, id',
    'name DESC NULLS LAST, id',
])
def test_nulls(env, countries, order):
    cities = env['test_orm.city'].create([
        {'name': 'not null 2', 'country_id': countries[2].id},
        {'name': 'not null 0', 'country_id': countries[0].id},
        {'name': False, 'country_id': countries[1].id},
        {'name': "", 'country_id': False},
        {'name': False, 'country_id': False},
        {'name': 'not null 1', 'country_id': countries[1].id},
    ])
    assert (env['test_orm.city'].search(
        [('id', 'in', cities.ids)], order=order).mapped('name')
        == cities.sorted(order).mapped('name'))


@pytest.mark.parametrize('order', ['name DESC', 'name ASC'])
def test_collation(env, order):
    countries = env['test_orm.country'].create([
        {'name': name} for name in (
            'é', 'e', 'É', '1.0', '1,0', '01', '10', '9', 'Ab', '👍', 'AB',
            'Aa', 'AA')])
    assert (countries.search([('id', 'in', countries.ids)], order=order)
            .mapped('name') == countries.sorted(order).mapped('name'))


@pytest.mark.parametrize('order', [
    'parent ASC, id ASC',
    'parent ASC, id DESC',
    'parent DESC, id ASC',
    'parent DESC, id DESC',
])
def test_sorted_recursion(env, order):
    categories = env['test_orm.category'].search([])
    assert (categories.search([('id', 'in', categories.ids)], order=order)
            .mapped('name') == categories.sorted(order).mapped('name'))


def test_compare_new_id():
    assert 5 < NewId()
    assert 3 < NewId(4)
    assert 5 > NewId(4)
    assert 5 >= NewId(4)
    assert 4 < NewId(4)
    assert NewId(5) > NewId(4)
