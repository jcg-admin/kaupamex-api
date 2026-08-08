"""Tests — addon ``sale_stock_margin`` (margen ponderado por entrega)."""
from decimal import Decimal

import pytest

from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale_margin.models import SaleOrderLineMargin
from addons.sale_stock.models import SaleOrderLineDelivery
from addons.sale_stock_margin.services import recompute_purchase_price
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.integration


def _line(qty=10, cost=Decimal('50.00')):
    product = make_product(
        name='Bolsa', price=Decimal('100.00'), standard_price=cost,
    )
    order = SaleOrder.objects.create()
    return SaleOrderLine.objects.create(
        order=order, product=product, price_unit=Decimal('100.00'),
        product_uom_qty=qty,
    )


def test_no_delivery_uses_standard_cost(db):
    line = _line()
    purch = recompute_purchase_price(line)
    assert purch == Decimal('50.00')
    assert line.margin.purchase_price == Decimal('50.00')


def test_full_delivery_uses_delivery_cost(db):
    line = _line(qty=10)
    SaleOrderLineDelivery.objects.create(line=line, qty_delivered=10)
    purch = recompute_purchase_price(line, delivered_unit_cost=Decimal('80.00'))
    assert purch == Decimal('80.00')


def test_partial_delivery_weighted_average(db):
    line = _line(qty=10, cost=Decimal('50.00'))
    SaleOrderLineDelivery.objects.create(line=line, qty_delivered=4)
    # (4*80 + 6*50) / 10 = 62.00
    purch = recompute_purchase_price(line, delivered_unit_cost=Decimal('80.00'))
    assert purch == Decimal('62.00')
    assert line.margin.purchase_price == Decimal('62.00')


def test_recompute_updates_existing_margin(db):
    line = _line(qty=10)
    # Primer cálculo crea el margen; segundo lo actualiza (no duplica).
    recompute_purchase_price(line)
    SaleOrderLineDelivery.objects.create(line=line, qty_delivered=10)
    recompute_purchase_price(line, delivered_unit_cost=Decimal('90.00'))
    line.refresh_from_db()
    assert line.margin.purchase_price == Decimal('90.00')
    assert SaleOrderLineMargin.objects.filter(line=line).count() == 1
