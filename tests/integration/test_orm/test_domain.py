"""Porte de ``odoo19c: odoo/addons/test_orm/tests/test_domain.py`` (parcial).

Revisión de referencia: ``odoo-tools@abe4040ec1``. Casos de optimización de
condiciones de ``TestDomain`` (``:402-473``) sobre ``test_orm.mixed``.

pendiente: el resto de ``TestDomain`` (``_search`` con complemento, fechas,
``like``, ``any`` con ``id``, desigualdades) y ``TestDomainOptimize``.
"""

from datetime import date, datetime
from itertools import combinations

import pytest
from django.contrib.auth import get_user_model

from orm.domains import Domain
from orm.environments import Environment, context_scope, sudo
from orm.utils import SUPERUSER_ID
from tools import date_utils
from tools.misc import OrderedSet

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

NUMBER_DOMAIN = Domain('number', '>', 5)


class _FrozenNow(datetime):
    """``datetime`` con ``now()`` fijo en ``2024-01-05 13:05:00`` UTC.

    La fuente usa ``freeze_time`` (``freezegun``), que no es dependencia de
    este proyecto; ``tools.date_utils`` resuelve ``'today'``/``'+12H'`` con
    ``datetime.now(utc)``, que es el único reloj que hay que fijar.
    """

    def __new__(cls, *args, **kwargs):
        # Lo que se construye por la clase es un ``datetime`` real: el doble
        # sólo fija el reloj, no el tipo de los valores del dominio.
        return datetime(*args, **kwargs)

    @classmethod
    def now(cls, tz=None):
        moment = datetime(2024, 1, 5, 13, 5, 0, tzinfo=date_utils.utc)
        return moment if tz is None else moment.astimezone(tz)


@pytest.fixture
def frozen_now(monkeypatch):
    monkeypatch.setattr(date_utils, 'datetime', _FrozenNow)


@pytest.fixture
def model(env):
    return env['test_orm.mixed']


def test_bool_optimize(model):
    assert Domain.TRUE.optimize(model) is Domain.TRUE
    assert Domain.FALSE.optimize(model) is Domain.FALSE


def test_condition_build():
    """Los términos no cambian al construir la condición."""
    dom = Domain('a', '=', 1)
    assert (dom.field_expr, dom.operator, dom.value) == ('a', '=', 1)
    dom = Domain('a', '=', [1, 2])
    assert (dom.field_expr, dom.operator, dom.value) == ('a', '=', [1, 2])
    assert Domain('a', 'in', 5).value == 5
    assert Domain('a', '=', []).value == []
    assert Domain('a', 'in', Domain.TRUE).operator == 'in'
    assert isinstance(Domain('a', 'any', [('x', '>', 1)]).value, list)


def test_condition_optimize_optimal(model):
    assert NUMBER_DOMAIN.optimize(model) is NUMBER_DOMAIN


def test_condition_optimize_invalid_field(model):
    with pytest.raises(ValueError):
        Domain('xxx_inexisting', '=', False).optimize(model)


def test_condition_optimize_traverse(model):
    assert Domain('currency_id.id', '>', 5).optimize(model) == Domain(
        'currency_id', 'any', Domain('id', '>', 5))
    assert (~Domain('currency_id.id', '>', 5)).optimize(model) == Domain(
        'currency_id', 'not any', Domain('id', '>', 5))


def test_condition_optimize_in(model):
    domain = Domain('id', 'in', range(5)).optimize(model)
    assert isinstance(domain.value, OrderedSet)
    domain = Domain('id', 'in', [9, 99]).optimize(model)
    assert isinstance(domain.value, OrderedSet)
    assert domain.optimize(model) is domain, 'Idempotent'
    assert Domain('id', 'in', []).optimize(model) == Domain.FALSE
    assert Domain('id', 'not in', []).optimize(model) == Domain.TRUE


def test_condition_optimize_any(env, model):
    """Con un ``QuerySet`` en el valor: aquí ``_search`` devuelve el
    ``QuerySet`` de Django, el equivalente del ``Query`` de la fuente."""
    Currency = env['res.currency']
    domain = Domain('currency_id', 'any!', Currency.objects.all())
    assert domain.optimize(model) is domain, 'Idempotent with a query value'
    assert Domain('currency_id', 'any', Domain.FALSE).optimize(
        model) == Domain.FALSE
    assert Domain('currency_id', 'not any', Domain.FALSE).optimize(
        model) == Domain.TRUE
    assert Domain('currency_id', 'any', Domain('id', 'not in', [])).optimize(
        model) == Domain('currency_id', 'any', Domain.TRUE)
    domain = Domain('currency_id', 'any', Domain('id', 'in', [1])).optimize(
        model)
    assert domain.optimize(model) is domain, 'Idempotent'


def test_condition_optimize_any_non_relational(model):
    with pytest.raises(ValueError):
        Domain('number', 'any', Domain('id', '>', 0)).optimize(model)


def test_condition_optimize_any_id(model):
    assert Domain('id', 'any', NUMBER_DOMAIN).optimize(model) == NUMBER_DOMAIN
    assert Domain('id', 'not any', NUMBER_DOMAIN).optimize(model) == (
        ~NUMBER_DOMAIN).optimize(model)


@pytest.fixture
def message(env):
    return env['test_orm.message']


def test_condition_optimize_like(message):
    domain = Domain('name', 'like', 'ok')
    assert domain.optimize(message) is domain, 'Idempotent'
    assert Domain('name', 'like', '').optimize(message) == Domain.TRUE
    assert Domain('name', 'not like', '').optimize(message) == Domain.FALSE
    assert Domain('name', '=like', '').optimize(message) == Domain(
        'name', '=', False).optimize(message)
    assert Domain('name', 'like', 5).optimize(message) == Domain(
        'name', 'like', '5')


def test_condition_optimize_like_relational(message):
    assert Domain('discussion', 'like', '').optimize(message) == Domain(
        'discussion', 'not in', OrderedSet([False]))
    domain = Domain('discussion', 'like', 'ok').optimize(message)
    assert domain.operator == 'any'
    assert isinstance(domain.value, Domain)
    assert domain.value.field_expr == 'display_name'
    domain = Domain('discussion', 'not like', 'ok').optimize(message)
    assert domain.operator == 'not any', (
        f'Always use positive operator on display_name; in {domain}')


def test_condition_optimize_bool(message):
    is_important = Domain('important', 'in', OrderedSet([True]))
    assert is_important.optimize(message) is is_important
    assert Domain('important', '=', True).optimize(message) == is_important
    assert list(Domain('important', 'not in', [True, False]).optimize(
        message)) == [('important', 'not in', [True, False])]
    assert Domain('important', 'not in', [True, False]).optimize_full(
        message) == Domain.FALSE
    assert Domain('important', 'in', [True, 'yes']).optimize(
        message) == is_important
    assert Domain('important', 'in', ['yes']).optimize(message) == is_important
    assert Domain('important', 'in', [0, 2]).optimize_full(
        message) == Domain.TRUE
    assert list(Domain('active', 'in', [True, False]).optimize(message)) == [
        ('active', 'in', [True, False])]
    assert Domain('active', 'in', [True, False]).optimize_full(
        message) == Domain.TRUE


def test_condition_optimize_date(model, frozen_now):
    in_jan_5 = Domain('date', 'in', OrderedSet([date(2024, 1, 5)]))
    assert Domain('date', '=', date(2024, 1, 5)).optimize(model) == in_jan_5
    assert Domain('date', '=', datetime(2024, 1, 5, 12, 0, 0)).optimize(
        model) == in_jan_5
    assert Domain('date', '=', '2024-01-05').optimize(model) == in_jan_5
    assert Domain('date', '=like', '2024%').optimize(model) == Domain(
        'date', '=like', '2024%')
    assert Domain('date', '>', '2024-01-01').optimize(model) == Domain(
        'date', '>', date(2024, 1, 1))
    assert Domain('date', '>', False).optimize(model) == Domain.FALSE
    assert Domain('date', 'not in', ['2024-01-05', date(2023, 1, 1)]).optimize(
        model) == Domain('date', 'not in', OrderedSet(
            [date(2024, 1, 5), date(2023, 1, 1)]))
    with pytest.raises(ValueError):
        Domain('date', '>', 'hello').optimize(model)
    # ≙ freeze_time('2024-01-05 13:05:00'): ver frozen_now
    domain = Domain('date', '>', 'today')
    assert domain.optimize(model) == domain
    assert domain.optimize_full(model) == Domain(
        'date', '>', date(2024, 1, 5))
    assert Domain('date', '>', '+12H').optimize_full(model) == Domain(
        'date', '>', date(2024, 1, 6))
    assert list(Domain('date', '=', 'today').optimize_full(
        model).value) == [date(2024, 1, 5)]


def test_condition_optimize_datetime(model, frozen_now):
    with context_scope(tz='UTC'):
        jan_5 = (Domain('moment', '<', datetime(2024, 1, 5, second=1))
                 & Domain('moment', '>=', datetime(2024, 1, 5)))
        assert Domain('moment', '=', date(2024, 1, 5)).optimize(
            model) == jan_5
        assert Domain('moment', '=', '2024-01-05').optimize(model) == jan_5
        assert Domain('moment', '=like', '2024%').optimize(model) == Domain(
            'moment', '=like', '2024%')
        assert Domain('moment', '>', '2024-01-01 10:00:00').optimize(
            model) == Domain('moment', '>=', datetime(2024, 1, 1, 10, second=1))
        assert Domain('moment', '>', '2024-01-01').optimize(model) == Domain(
            'moment', '>=', datetime(2024, 1, 2))
        assert Domain('moment', '<', '2024-01-01').optimize(model) == Domain(
            'moment', '<', datetime(2024, 1, 1))
        assert Domain('moment', '<=', '2024-01-01').optimize(model) == Domain(
            'moment', '<', datetime(2024, 1, 2))
        assert Domain('moment', '>', False).optimize(model) == Domain.FALSE
        assert Domain('moment', 'not in', [
            '2024-01-05', datetime(2023, 1, 1)]).optimize(model) == (
            Domain('moment', 'in', OrderedSet([False]))
            | Domain('moment', '<', datetime(2024, 1, 5))
            | Domain('moment', '>=', datetime(2024, 1, 5, second=1))
        ) & (
            Domain('moment', 'in', OrderedSet([False]))
            | Domain('moment', '<', datetime(2023, 1, 1))
            | Domain('moment', '>=', datetime(2023, 1, 1, second=1))
        )
        with pytest.raises(ValueError):
            Domain('moment', '>', 'hello').optimize(model)
        # ≙ freeze_time('2024-01-05 13:05:00'): ver frozen_now
        domain = Domain('moment', '>=', 'today')
        assert domain.optimize(model) == domain
        assert domain.optimize_full(model) == Domain(
            'moment', '>=', datetime(2024, 1, 5))
        assert Domain('moment', '>=', '+12H').optimize_full(
            model) == Domain('moment', '>=', datetime(2024, 1, 6, 1, 5))


# ---------------------------------------------------------------------------
# Desigualdades — ≙ ``TestDomain.test_inequalities_*`` (``:344-400``) con el
# ayudante ``TransactionExpressionCase._search`` (``odoo19c: odoo/addons/base/
# tests/test_expression.py:15-48``): la búsqueda SQL y ``filtered_domain`` en
# memoria dan las mismas filas, y el dominio y su complemento cubren todo.
# ---------------------------------------------------------------------------


def _check_search(model, domain, in_memory=True):
    sql = model.search(domain, order='id')
    universe = model.search([], order='id')
    if in_memory:
        in_memory_result = universe.filtered_domain(domain)
        assert sql._ids == in_memory_result._ids, (
            f'filtered_domain no coincide con la búsqueda SQL: {domain}')
    complement = model.search(~Domain(domain), order='id')
    assert sorted(sql._ids + complement._ids) == sorted(universe._ids), (
        f'{domain} y su complemento no cubren todo')
    return sql


@pytest.mark.parametrize(('operator', 'value'), [
    ('>', 2), ('>', -2), ('<', 1), ('<=', 1)])
def test_inequalities_int(env, operator, value):
    Model = env['test_orm.empty_int']
    Model.create([{}])
    Model.create([{'number': n} for n in range(-5, 6)])
    _check_search(Model, [('number', operator, value)])


@pytest.mark.parametrize(('operator', 'value'), [
    ('>', 'a'), ('>', 'z'), ('<', 'k'), ('<=', 'k'), ('<', '')])
def test_inequalities_char(env, operator, value):
    Model = env['test_orm.empty_char']
    Model.create([{}])
    Model.create([{'name': n} for n in (False, '', 'hello', 'world')])
    _check_search(Model, [('name', operator, value)])


_NAIVE_DATETIME = pytest.mark.xfail(strict=True, reason=(
    'H-API-1130: un datetime naive se interpreta en TIME_ZONE al escribir y '
    'en SQL, y filtered_domain lo compara contra el aware leído; en la fuente '
    'un Datetime es naive en UTC. Sucesor: TASK-API-0190.'))


@pytest.mark.parametrize(('operator', 'day'), [
    pytest.param('>', 3, marks=_NAIVE_DATETIME),
    pytest.param('>', 8, marks=_NAIVE_DATETIME),
    ('>', 20),
    pytest.param('<', 7, marks=_NAIVE_DATETIME),
    pytest.param('<=', 7, marks=_NAIVE_DATETIME),
])
def test_inequalities_datetime(env, operator, day):
    Model = env['test_orm.mixed']
    Model.create([{}])
    Model.create([{'moment': datetime(2000, 5, n)} for n in range(5, 10)])
    _check_search(Model, [('moment', operator, datetime(2000, 5, day))])


def test_condition_optimize_maybe_eq(model):
    assert Domain('number', '=?', 5).optimize(model) == Domain(
        'number', '=', 5).optimize(model)
    assert Domain('number', '=?', 0).optimize(model) == Domain.TRUE


def test_condition_optimize_child_parent_of(env):
    model = env['test_orm.category']
    categ = model.create({'name': 'parent'})
    categ_child = model.create({'name': 'child', 'parent': categ.id})
    categ = model.browse(categ.ids)
    assert Domain('id', 'child_of', categ.ids).optimize_full(model) == Domain(
        'parent_path', '=like', f'{categ.parent_path}%')
    assert Domain('id', 'parent_of', categ_child.ids).optimize_full(
        model) == Domain('id', 'in', OrderedSet([categ_child.id, categ.id]))


def test_not_optimize():
    assert ~~NUMBER_DOMAIN == NUMBER_DOMAIN


def test_nary_build():
    assert ~(NUMBER_DOMAIN & NUMBER_DOMAIN) == ~NUMBER_DOMAIN | ~NUMBER_DOMAIN
    assert ~(NUMBER_DOMAIN | NUMBER_DOMAIN) == ~NUMBER_DOMAIN & ~NUMBER_DOMAIN


# ---------------------------------------------------------------------------
# ``TestDomainOptimize`` (``:780-990``), casos sobre campos ya portados.
# ---------------------------------------------------------------------------


def test_nary_optimize_in(model):
    def domain(op, values):
        if not values:
            return Domain.FALSE if op == 'in' else Domain.TRUE
        return Domain('number', op, values)

    set123 = OrderedSet([1, 2, 3])
    set345 = OrderedSet([3, 4, 5])
    set910 = OrderedSet([9, 10])
    sets = [set123, set345, set910, OrderedSet()]
    for a, b in (list(combinations(sets, 2))
                 + list(combinations(reversed(sets), 2))):
        assert (domain('in', a) | domain('in', b)).optimize(model) == domain(
            'in', a | b), f'in: {a} | {b}'
        assert (domain('in', a) & domain('in', b)).optimize(model) == domain(
            'in', a & b), f'in: {a} & {b}'
        assert (domain('not in', a) | domain('not in', b)).optimize(
            model) == domain('not in', a & b), f'not in {a} | not in {b}'
        assert (domain('not in', a) & domain('not in', b)).optimize(
            model) == domain('not in', a | b), f'not in {a} & not in {b}'
        assert (domain('in', a) | domain('not in', b)).optimize(
            model) == domain('not in', b - a), f'in {a} | not in {b}'
        assert (domain('in', a) & domain('not in', b)).optimize(
            model) == domain('in', a - b), f'in {a} & not in {b}'
    assert (domain('in', set123) | domain('not in', set910)
            | domain('in', set345)).optimize(model) == domain(
        'not in', set910)
    assert (domain('in', set123) & domain('not in', set345)
            & domain('in', [1])).optimize(model) == domain(
        'in', OrderedSet([1]))
    assert (~(domain('in', set123) | domain('in', set345))).optimize(
        model) == domain('not in', set123 | set345)
    assert (~(domain('in', set123) & domain('in', set345))).optimize(
        model) == domain('not in', set123 & set345)
    assert isinstance((Domain('number', 'in', [1]) | Domain(
        'number', 'in', [2])).optimize(model).value, OrderedSet)


def test_nary_optimize_same(model):
    assert (NUMBER_DOMAIN & NUMBER_DOMAIN).optimize(model) == NUMBER_DOMAIN


def test_condition_optimize_search(env):
    """≙ ``:432-443``: el ``search`` del campo sustituye la condición."""
    model = env['test_orm.bar']
    foo = env['test_orm.foo'].create({'name': 'ok'})
    assert Domain('foo', '=', foo.id).optimize_full(model) == Domain(
        'name', 'in', ['ok']).optimize(model)
    assert Domain('foo', 'in', env['test_orm.foo'].browse().ids).optimize(
        model) == Domain.FALSE, 'search should be further optimized'


def test_optimize_level_by_level(env, monkeypatch):
    """≙ ``:979-989``: el ``search`` se llama una vez con los valores
    agrupados."""
    def search_foo(model, operator, value):
        return [('name', '=', str(tuple(value)))]

    monkeypatch.setattr(type(env['test_orm.bar']), '_search_foo',
                        classmethod(search_foo))
    domain = Domain('foo', '=', 4) | Domain('foo', '=', 5)
    assert domain.optimize_full(env['test_orm.bar']) == Domain(
        'name', 'in', OrderedSet(['(4, 5)']))


def test_bypass_comodel_id_lookup(env, model):
    """≙ ``:991-1014``: con elevación, ``currency_id.id`` se resuelve sobre la
    columna, sin subconsulta; sin ella, queda la subconsulta con reglas. La
    fuente lo mide con ``@users('admin')``; aquí, con un usuario declarado."""
    user = get_user_model().objects.create_user(
        login='bypass.lookup@kaupamex.mx', password='Bypass123!')
    if user.pk == SUPERUSER_ID:
        user = get_user_model().objects.create_user(
            login='bypass.lookup.2@kaupamex.mx', password='Bypass123!')
    with Environment(None, user.pk, {}):
        assert list(Domain('currency_id.id', '=', 2).optimize_full(
            model)) == [('currency_id', 'any', [('id', 'in', [2])])]
    with sudo():
        assert list(Domain('currency_id.id', '=', 2).optimize_full(
            model)) == [('currency_id', 'in', [2])]
        assert list(Domain('currency_id.id', 'in', [2, False]).optimize_full(
            model)) == [('currency_id', 'in', [2])]
        assert list(Domain('currency_id.id', 'not in', [2]).optimize_full(
            model)) == [('currency_id', 'not in', [2, False])]


# ---------------------------------------------------------------------------
# ``test_anys_many2one`` y ``_implicit`` (``:202-276``). La fuente crea los
# hijos con ``Command.create`` dentro del padre; aquí se crean aparte, porque
# leer ``child_ids`` todavía devuelve el gestor de Django (TASK-API-0190).
# ---------------------------------------------------------------------------


@pytest.fixture
def any_family(env):
    Parent, Child = env['test_orm.any.parent'], env['test_orm.any.child']
    jean, clude = Parent.create([{'name': 'Jean'}, {'name': 'Clude'}])

    def child(parent, quantity):
        return Child.create({'parent_id': parent.id, 'quantity': quantity})

    j1, j10, c2, c20 = (child(jean, 1), child(jean, 10), child(clude, 2),
                        child(clude, 20))
    j1.write({'link_sibling_id': j10.id})
    c20.write({'link_sibling_id': c2.id})
    return jean, clude, (j1, j10, c2, c20)


def _ids(records):
    return sorted(records._ids)


def test_any_on_many2one(env, any_family):
    """≙ ``test_anys_many2one`` de la fuente."""
    _, _, (j1, j10, c2, c20) = any_family
    Child = env['test_orm.any.child']
    found = _check_search(Child, [('link_sibling_id', 'any',
                                   [('quantity', '>', 5)])])
    assert _ids(found) == [j1.id]
    found = _check_search(Child, [('link_sibling_id', 'not any',
                                   [('quantity', '>', 5)])])
    assert _ids(found) == sorted([j10.id, c2.id, c20.id])
    found = _check_search(Child, [('parent_id', 'any',
                                   [('name', '=', 'Jean')])])
    assert _ids(found) == sorted([j1.id, j10.id])
    found = _check_search(Child, [('parent_id', 'not any',
                                   [('name', '=', 'Jean')])])
    assert _ids(found) == sorted([c2.id, c20.id])


def test_any_on_many2one_implicit(env, any_family):
    """≙ ``test_anys_many2one_implicit`` de la fuente."""
    jean, clude, _ = any_family
    Parent = env['test_orm.any.parent']
    assert _ids(_check_search(Parent, [('child_ids.quantity', '=', 1)])) == [
        jean.id]
    assert _ids(_check_search(Parent, [('child_ids.quantity', '>', 15)])) == [
        clude.id]
