"""Tests — addon ``sale_margin`` (costo + margen por línea)."""
from decimal import Decimal

import pytest

from addons.catalogue.models import Category, Product
from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale_margin.models import SaleOrderLineMargin

pytestmark = pytest.mark.integration


@pytest.fixture
def producto(db):
    cat = Category.objects.create(name='Cat M', slug='cat-margin', is_active=True)
    p = Product.objects.create(
        name='Prod M', slug='prod-margin', sku='MRG-001',
        description='', price=Decimal('100.00'), cost=Decimal('60.00'), stock=5,
        is_active=True, is_published=True,
    )
    p.categories.add(cat)
    return p


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
    producto.cost = Decimal('80.00'); producto.save()
    m.refresh_from_db()
    assert m._cost_snapshot() == Decimal('60.00')


def test_margin_zero_subtotal(producto):
    so = SaleOrder.objects.create()
    line = SaleOrderLine.objects.create(order=so, product=producto, product_uom_qty=1, price_unit=Decimal('0.00'))
    m = SaleOrderLineMargin.objects.create(line=line)
    assert m.margin_percent() == Decimal('0.00')
