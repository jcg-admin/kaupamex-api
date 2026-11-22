"""``sale.order.line`` sobre ``BaseModel``.

≙ ``odoo19c: addons/sale/models/sale_order_line.py:13``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
sale-basemodel-u3a-order-line.md``.

*Métrica:* la base de la clase, el total de la orden tras borrar una línea
por ``unlink`` y el valor de un Many2one nulo.
*Ciega a:* la guarda ``_unlink_except_confirmed`` de la fuente, que porta
U3c, y a los accesores que cambian al adoptar ``sale.order`` (U3b).
"""
from decimal import Decimal

import pytest

from addons.sale.models import SaleOrder, SaleOrderLine
from orm.environments import sudo
from orm.models import BaseModel
from tests.factories.order_factory import STATUS_DRAFT, make_order
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _elevated():
    with sudo():
        yield


@pytest.fixture
def order(user):
    # Borrador: una orden confirmada no deja borrar sus líneas
    # (``_unlink_except_confirmed``, U3c).
    return make_order(status=STATUS_DRAFT, user=user)


def _line(order, price, name='Hora'):
    product = make_product(name=name)
    return SaleOrderLine.objects.create(
        order=order, product=product, name=product.name,
        price_unit=Decimal(price), product_uom_qty=1)


def test_the_line_is_a_base_model():
    assert issubclass(SaleOrderLine, BaseModel)


def test_unlinking_a_line_recomputes_its_order(order):
    _line(order, '100.00', name='Hora A')
    second = _line(order, '50.00', name='Hora B')
    assert SaleOrder.objects.get(pk=order.pk).amount_total == Decimal('150.00')
    second.unlink()
    assert not SaleOrderLine.objects.filter(pk=second.pk).exists()
    assert SaleOrder.objects.get(pk=order.pk).amount_total == Decimal('100.00')


def test_a_line_without_product_has_an_empty_product(order):
    line = SaleOrderLine.objects.create(
        order=order, name='Nota', display_type='line_note',
        price_unit=Decimal('0'), product_uom_qty=0)
    assert not line.product
    assert line.product is not None
