"""
Tests — addons ``purchase`` + ``sale_purchase`` (venta de servicio → compra).
"""

from decimal import Decimal

import pytest

from addons.base.models import ResPartner
from addons.purchase.models import PurchaseOrder, PurchaseOrderLine
from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale_purchase.models import SaleLinePurchaseLink
from orm.environments import sudo
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _as_superuser():
    """Sobre ``BaseModel`` la orden de compra aplica su control de acceso;
    los datos de prueba de la referencia se escriben como superusuario."""
    with sudo():
        yield


_vendor_seq = [0]


def _vendor():
    """El proveedor es un contacto (``odoo19c: purchase_order.py:91-94``)."""
    _vendor_seq[0] += 1
    return ResPartner.objects.create(name=f'Proveedor {_vendor_seq[0]}')


def test_purchase_order_confirm_state_machine(db):
    product = make_product(name='Insumo', price=Decimal('58.00'))
    po = PurchaseOrder.objects.create(partner_id=_vendor())
    PurchaseOrderLine.objects.create(
        order_id=po, product_id=product, price_unit=Decimal('58.00')
    )
    po.button_confirm()
    assert po.state == PurchaseOrder.STATE_PURCHASE
    # ``objects.create`` no pasa por el ``create`` del ORM: el nombre se
    # queda en el valor por defecto de la fuente.
    assert po.name == 'New'
    assert po.date_order is not None


def test_purchase_line_tax_breakdown(db):
    product = make_product(name='Insumo', price=Decimal('116.00'))
    po = PurchaseOrder.objects.create(partner_id=_vendor())
    line = PurchaseOrderLine.objects.create(
        order_id=po,
        product_id=product,
        price_unit=Decimal('116.00'),
        product_qty=2,
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
        order=order,
        product=product,
        price_unit=Decimal('300.00'),
        product_uom_qty=3,
        name='Servicio subcontratado',
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
        order=order,
        product=product,
        price_unit=Decimal('100.00'),
        name='S',
    )
    vendor = _vendor()
    SaleLinePurchaseLink.generate_purchase(sale_line, vendor)
    SaleLinePurchaseLink.generate_purchase(sale_line, vendor)
    # One2many: una línea de venta puede generar varias de compra (Odoo).
    assert SaleLinePurchaseLink.purchase_line_count(sale_line) == 2
    assert PurchaseOrder.objects.count() == 2
