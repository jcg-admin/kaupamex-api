"""Porte de ``odoo19c: odoo/addons/test_orm/tests/test_domain.py`` (parcial).

Revisión de referencia: ``odoo-tools@abe4040ec1``. Casos de optimización de
condiciones de ``TestDomain`` (``:402-473``) sobre ``test_orm.mixed``.

pendiente: el resto de ``TestDomain`` (``_search`` con complemento, fechas,
``like``, ``any`` con ``id``, desigualdades) y ``TestDomainOptimize``.
"""

import pytest

from orm.domains import Domain
from tools.misc import OrderedSet

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

NUMBER_DOMAIN = Domain('number', '>', 5)


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
