"""``sale.order`` sobre ``BaseModel``.

≙ ``odoo19c: addons/sale/models/sale_order.py:35``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
sale-basemodel-u3b-order.md``.

*Métrica:* la base de la clase, el tipo de ``order.order_line``, el total
tras un borrado en bloque por ``unlink`` y el descriptor sembrado del
reporte.
*Ciega a:* las guardas de borrado y las restricciones de la fuente, que porta
U3c, y a los reversos desde apps que aún no son ``BaseModel``.
"""
from decimal import Decimal

import pytest

from addons.base.models import IrUiView
from addons.sale.data.report_templates import REPORT_SALEORDER_KEY
from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale_loyalty.models.sale_order_coupon import SaleOrderCoupon
from addons.sale_stock.models.sale_order import SaleOrderDelivery
from addons.sale_stock.models.sale_order_line import SaleOrderLineDelivery
from orm.environments import sudo
from orm.models import BaseModel
from tests.factories.order_factory import make_order
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _elevated():
    with sudo():
        yield


@pytest.fixture
def order(user):
    return make_order(user=user)


def _line(order, price, name):
    product = make_product(name=name)
    return SaleOrderLine.objects.create(
        order=order, product=product, name=product.name,
        price_unit=Decimal(price), product_uom_qty=1)


def test_the_order_is_a_base_model():
    assert issubclass(SaleOrder, BaseModel)


def test_order_line_is_a_recordset_of_its_lines(order):
    first = _line(order, '10.00', 'U3b A')
    second = _line(order, '20.00', 'U3b B')
    lines = order.order_line
    assert isinstance(lines, SaleOrderLine)
    assert sorted(lines.ids) == sorted([first.pk, second.pk])


def test_unlinking_lines_in_bulk_recomputes_the_order(order):
    _line(order, '100.00', 'U3b C')
    _line(order, '50.00', 'U3b D')
    order.order_line.unlink()
    assert SaleOrder.objects.get(pk=order.pk).amount_total == Decimal('0.00')


def test_the_report_template_iterates_the_recordset():
    arch = IrUiView.objects.get(key=REPORT_SALEORDER_KEY).arch_db
    assert 'docs.order_line.all' not in arch
    assert 'in="docs.order_line"' in arch


def test_archived_products_are_read_through_the_recordset(order):
    """≙ ``_compute_has_archived_products``
    (``odoo19c: addons/sale/models/sale_order.py:345``)."""
    line = _line(order, '10.00', 'U3b archivado')
    assert order._compute_has_archived_products() is False
    line.product.active = False
    line.product.save()
    assert order._compute_has_archived_products() is True


def test_the_coupon_base_skips_delivery_and_reward_lines(order):
    """La base del cupón suma sólo productos: filtra el recordset de líneas."""
    product_line = _line(order, '40.00', 'U3b producto')
    delivery = _line(order, '15.00', 'U3b envío')
    delivery.is_delivery = True
    delivery.save()
    reward = _line(order, '-5.00', 'U3b recompensa')
    reward.is_reward = True
    reward.save()
    coupon = SaleOrderCoupon(order=order)
    product_line.refresh_from_db()
    assert coupon.discount_base() == product_line.price_subtotal


def test_the_delivery_status_reads_the_line_deliveries(order):
    """≙ ``_compute_delivery_status``
    (``odoo19c: addons/sale_stock/models/sale_order.py:91``)."""
    status = SaleOrderDelivery(order=order)
    line = _line(order, '10.00', 'U3b entregable')
    assert status.compute_status() is None
    SaleOrderLineDelivery.objects.create(line=line, qty_delivered=0)
    assert status.compute_status() == SaleOrderDelivery.STATUS_PENDING
    SaleOrderLineDelivery.objects.filter(line=line).update(qty_delivered=1)
    assert status.compute_status() == SaleOrderDelivery.STATUS_FULL
