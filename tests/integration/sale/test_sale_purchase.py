"""Tests — addons ``purchase`` + ``sale_purchase`` (venta de servicio → compra)."""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from addons.purchase.models import PurchaseOrder, PurchaseOrderLine
from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale_purchase.models import SaleLinePurchaseLink
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.integration

User = get_user_model()

_vendor_seq = [0]


def _vendor():
    _vendor_seq[0] += 1
    return User.objects.create_user(
        login=f'prov{_vendor_seq[0]}@practicayoruba.mx', password='x')


def test_purchase_order_confirm_state_machine(db):
    product = make_product(name='Insumo', price=Decimal('58.00'))
    po = PurchaseOrder.objects.create(partner_id=_vendor())
    # No se puede confirmar sin líneas.
    with pytest.raises(ValidationError):
        po.button_confirm()
    PurchaseOrderLine.objects.create(order_id=po, product_id=product, price_unit=Decimal('58.00'))
    po.button_confirm()
    assert po.state == PurchaseOrder.STATE_PURCHASE
    assert po.name.startswith('P-')
    assert po.date_order is not None


def test_purchase_line_tax_breakdown(db):
    product = make_product(name='Insumo', price=Decimal('116.00'))
    po = PurchaseOrder.objects.create(partner_id=_vendor())
    line = PurchaseOrderLine.objects.create(
        order_id=po, product_id=product, price_unit=Decimal('116.00'), product_qty=2,
    )
    # IVA 16% incluido: total 232.00 → tax 32.00 → subtotal 200.00.
    assert line.price_total() == Decimal('232.00')
    assert line.price_tax() == Decimal('32.00')
    assert line.price_subtotal() == Decimal('200.00')
    assert po.amount_total() == Decimal('232.00')
    assert po.amount_untaxed() == Decimal('200.00')


def test_generate_purchase_from_sale_line(db):
    product = make_product(name='Servicio a comprar', price=Decimal('300.00'))
    order = SaleOrder.objects.create()
    sale_line = SaleOrderLine.objects.create(
        order=order, product=product, price_unit=Decimal('300.00'),
        product_uom_qty=3, name='Servicio subcontratado',
    )
    vendor = _vendor()
    link = SaleLinePurchaseLink.generate_purchase(sale_line, vendor)
    assert link.purchase_line.product_id == product
    assert link.purchase_line.product_qty == 3
    assert link.purchase_line.price_unit == Decimal('300.00')
    assert link.purchase_line.order_id.partner_id == vendor
    # Trazabilidad venta→compra (Odoo sale_line_id / purchase_line_ids).
    assert sale_line.purchase_links.count() == 1
    assert SaleLinePurchaseLink.purchase_line_count(sale_line) == 1
    assert link.purchase_line.sale_link == link


def test_generate_purchase_twice_counts_two(db):
    product = make_product(name='Servicio', price=Decimal('100.00'))
    order = SaleOrder.objects.create()
    sale_line = SaleOrderLine.objects.create(
        order=order, product=product, price_unit=Decimal('100.00'), name='S',
    )
    vendor = _vendor()
    SaleLinePurchaseLink.generate_purchase(sale_line, vendor)
    SaleLinePurchaseLink.generate_purchase(sale_line, vendor)
    # One2many: una línea de venta puede generar varias de compra (Odoo).
    assert SaleLinePurchaseLink.purchase_line_count(sale_line) == 2
    assert PurchaseOrder.objects.count() == 2
