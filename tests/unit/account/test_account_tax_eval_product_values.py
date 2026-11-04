"""Los valores de producto y unidad que ve una fórmula de impuesto.

≙ los ocho ``_eval_taxes_computation_*`` de producto y unidad (``odoo19c:
addons/account/models/account_tax.py:731-895``, LGPL-3) y su uso en
``_get_tax_details`` (``:1241-1244``), que llena
``evaluation_context['product']`` y ``['uom']``. En ``account`` los ganchos
de campos devuelven el conjunto vacío; ``account_tax_python`` los extiende.
"""

from decimal import Decimal

import pytest

from addons.account.models import AccountTax
from addons.base.models import ResCompany
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db


@pytest.fixture
def taxes(db):
    company = ResCompany.objects.create(code='eval-producto',
                                        name='Eval producto')
    tax = AccountTax.objects.create(name='IVA', amount=Decimal('16'),
                                    company=company)
    return AccountTax.objects.filter(pk=tax.pk)


def test_without_formulas_the_field_hooks_are_empty(taxes):
    assert taxes._eval_taxes_computation_prepare_product_fields() == set()
    assert taxes._eval_taxes_computation_prepare_product_uom_fields() == set()


def test_the_default_values_follow_the_field_type(taxes):
    defaults = taxes._eval_taxes_computation_prepare_product_default_values(
        {'volume', 'standard_price'})
    assert defaults == {
        'volume': {'type': 'float', 'default_value': 0.0},
        'standard_price': {'type': 'monetary', 'default_value': 0.0},
    }
    uom_defaults = (
        taxes._eval_taxes_computation_prepare_product_uom_default_values(
            {'factor'}))
    assert uom_defaults == {'factor': {'type': 'float', 'default_value': 0.0}}


def test_the_product_values_read_the_product_or_the_default(taxes):
    defaults = taxes._eval_taxes_computation_prepare_product_default_values(
        {'volume'})
    product = make_product(name='Eleke volumen', volume=12.5)
    assert taxes._eval_taxes_computation_prepare_product_values(
        defaults, product) == {'volume': 12.5}
    assert taxes._eval_taxes_computation_prepare_product_values(
        defaults, None) == {'volume': 0.0}


def test_turn_to_values_without_fields_is_empty(taxes):
    product = make_product(name='Eleke sin campos')
    assert taxes._eval_taxes_computation_turn_to_product_values(
        product=product) == {}
    assert taxes._eval_taxes_computation_turn_to_product_uom_values(
        product_uom=None) == {}


def test_the_engine_puts_product_and_uom_in_the_context(taxes, monkeypatch):
    seen = {}

    def spy(self, batch, raw_base, evaluation_context):
        seen.update(evaluation_context)
        return Decimal('0')

    monkeypatch.setattr(AccountTax, '_eval_tax_amount_price_excluded', spy)
    product = make_product(name='Eleke contexto')
    taxes._get_tax_details(Decimal('10'), product=product)
    assert seen['product'] == {}
    assert seen['uom'] == {}
    assert seen['price_unit'] == Decimal('10')
