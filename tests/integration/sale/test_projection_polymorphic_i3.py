"""Tests — I3: la proyección de estado sobre la venta canónica.

``order_status(order)`` es el punto por el que pasa TODO consumidor del
estado proyectado (verificado con ``grep -rn "order_status(" src/addons``).
I3 lo volvió polimórfico (patrón strangler) para que aceptara el espejo
``orders.Order`` o la ``SaleOrder`` canónica durante la migración.

Post-E5 (retiro del addon espejo ``orders``, ``api@77bd1f0``): ya no hay
espejo que desreferenciar — ``SaleOrder`` es la única entrada, y es la que
este módulo prueba. La clase ``TestUnaVentaSinEspejoSeProyectaIgual`` ya
cubría este caso ("la norma", según su propio docstring); se conserva como
única clase y se retira la duplicación espejo/canónica de
``TestElProyectorAceptaAmbosLados``.
"""
from decimal import Decimal
from uuid import uuid4

import pytest

from addons.payment.models import Payment
from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale.status_projection import (
    STATUS_CANCELLED,
    STATUS_PAID,
    STATUS_PENDING,
    order_status,
)
from tests.factories.product_factory import make_category, make_product

pytestmark = pytest.mark.django_db

ADDR = {
    'recipient_name': 'I3', 'street': 'Calle 3', 'city': 'CDMX',
    'state': 'CDMX', 'zip_code': '01000',
}


@pytest.fixture
def producto():
    cat = make_category(name='Cat I3')
    return make_product(name='Prod I3', price=Decimal('40.00'), stock=9, categ=cat)


class TestLaProyeccionSobreLaVentaCanonica:
    """El caso que E5 vuelve la norma: no hay fila espejo que desreferenciar."""

    def test_venta_proyecta_su_estado_a_lo_largo_del_ciclo(self, producto):
        venta = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, cart_token=uuid4())
        SaleOrderLine.objects.create(
            order=venta, product=producto, name=producto.name,
            product_uom_qty=1, price_unit=producto.lst_price)
        venta.action_confirm()
        assert order_status(venta) == STATUS_PENDING

        Payment.objects.create(
            sale_order=venta, gateway=Payment.GATEWAY_MANUAL,
            status=Payment.STATUS_APPROVED, amount=Decimal('40.00'))
        assert order_status(venta) == STATUS_PAID

    def test_venta_cancelada_proyecta_cancelled(self, producto):
        venta = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, cart_token=uuid4())
        SaleOrderLine.objects.create(
            order=venta, product=producto, name=producto.name,
            product_uom_qty=1, price_unit=producto.lst_price)
        venta.action_confirm()
        venta.action_cancel()
        assert order_status(venta) == STATUS_CANCELLED
