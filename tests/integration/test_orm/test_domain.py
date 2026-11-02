"""Porte de ``odoo19c: odoo/addons/test_orm/tests/test_domain.py`` (parcial).

Revisión de referencia: ``odoo-tools@abe4040ec1``. Casos de optimización de
condiciones de ``TestDomain`` (``:402-473``) sobre ``test_orm.mixed``.

pendiente: el resto de ``TestDomain`` (``_search`` con complemento, fechas,
``like``, ``any`` con ``id``, desigualdades) y ``TestDomainOptimize``.
"""

from datetime import date, datetime

import pytest

from orm.domains import Domain
from orm.environments import context_scope
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


@pytest.mark.xfail(strict=True, reason=(
    'Divergencia: aquí el search del campo (display_name -> _rec_name) se '
    'despacha en cualquier nivel; la fuente sólo en FULL '
    '(odoo19c: odoo/orm/domains.py:946-967), así que optimize() ya devuelve '
    'name. Restringirlo a FULL cambia pruebas que fijan la conducta actual '
    '(tests/unit/orm/test_field_search_method.py). Sucesor: TASK-API-0190.'))
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
