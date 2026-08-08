"""Tests — addon ``sale_margin`` (costo + margen por línea)."""
from decimal import Decimal

import pytest

from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale_margin.models import SaleOrderLineMargin
from tests.factories.product_factory import make_category, make_product

pytestmark = pytest.mark.integration


@pytest.fixture
def producto(db):
    cat = make_category(name='Cat M')
    return make_product(
        name='Prod M', price=Decimal('100.00'), stock=5, categ=cat,
        standard_price=Decimal('60.00'),
    )


def test_margin_from_product_cost(producto):
    so = SaleOrder.objects.create()
    line = SaleOrderLine.objects.create(order=so, product=producto, product_uom_qty=2, price_unit=Decimal('100.00'))
    m = SaleOrderLineMargin.objects.create(line=line)
    # subtotal (untaxed) de 2×100 IVA-incl 16% = 172.41; costo 60×2 = 120
    assert line.price_subtotal() == Decimal('172.41')
    assert m.margin() == Decimal('52.41')
    assert m.margin_percent() == Decimal('30.40')


def test_capture_purchase_price_snapshot(producto):
    so = SaleOrder.objects.create()
    line = SaleOrderLine.objects.create(order=so, product=producto, product_uom_qty=1, price_unit=Decimal('100.00'))
    m = SaleOrderLineMargin.objects.create(line=line)
    assert m.purchase_price is None
    m.capture_purchase_price()
    assert m.purchase_price == Decimal('60.00')
    # cambiar el costo del producto no altera el snapshot ya congelado
    producto.standard_price = Decimal('80.00')
    producto.save()
    m.refresh_from_db()
    assert m._cost_snapshot() == Decimal('60.00')


def test_margin_zero_subtotal(producto):
    so = SaleOrder.objects.create()
    line = SaleOrderLine.objects.create(order=so, product=producto, product_uom_qty=1, price_unit=Decimal('0.00'))
    m = SaleOrderLineMargin.objects.create(line=line)
    assert m.margin_percent() == Decimal('0.00')
