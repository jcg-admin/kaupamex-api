"""Tests — I3: la proyección de estado acepta la canónica (cuello de botella).

``order_status(order)`` es el punto por el que pasa TODO consumidor del
estado proyectado (37 llamadas en producción, verificado con
``grep -rn "order_status(" src/addons``). Hoy exige un ``orders.Order`` —
lo desreferencia como ``order.sale_order``. Mientras sea así, ningún
consumidor puede migrar su query al canónico de forma independiente: o
migran todos a la vez, o ninguno.

I3 lo vuelve **polimórfico** (patrón strangler, igual que el puente):
acepta el espejo o la ``SaleOrder`` canónica y proyecta el mismo estado.
Así cada consumidor migra su propia query cuando le toque su rebanada,
sin coordinación global y sin tocar la llamada al proyector.
"""
from decimal import Decimal
from uuid import uuid4

import pytest
from django.utils import timezone

from addons.catalogue.models import Category, Product
from addons.orders.status_projection import (
    STATUS_CANCELLED,
    STATUS_PAID,
    STATUS_PENDING,
    order_status,
)
from addons.payment.models import Payment
from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale.services import add_item_to_draft, confirm_draft_order

pytestmark = pytest.mark.django_db

ADDR = {
    'recipient_name': 'I3', 'street': 'Calle 3', 'city': 'CDMX',
    'state': 'CDMX', 'zip_code': '01000',
}


@pytest.fixture
def producto():
    cat = Category.objects.create(name='Cat I3', slug='cat-i3', is_active=True)
    prod = Product.objects.create(
        name='Prod I3', slug='prod-i3', sku='SKU-I3',
        price=Decimal('40.00'), stock=9, is_active=True, is_published=True)
    prod.categories.add(cat)
    return prod


@pytest.fixture
def par(producto):
    """(canónica, espejo) de una venta confirmada por el flujo real."""
    draft = SaleOrder.objects.create(
        state=SaleOrder.STATE_DRAFT, cart_token=uuid4())
    add_item_to_draft(draft, producto, quantity=1)
    legacy = confirm_draft_order(draft, address_data=dict(ADDR),
                                 guest_email='i3@test.mx')
    draft.refresh_from_db()
    return draft, legacy


class TestElProyectorAceptaAmbosLados:

    def test_mismo_estado_desde_el_espejo_y_desde_la_canonica(self, par):
        canonical, legacy = par
        assert order_status(legacy) == order_status(canonical) == STATUS_PENDING

    def test_sigue_coincidiendo_tras_avanzar_el_eje_de_pago(self, par):
        canonical, legacy = par
        Payment.objects.create(
            sale_order=canonical, order=legacy,
            gateway=Payment.GATEWAY_MANUAL,
            status=Payment.STATUS_APPROVED, amount=Decimal('40.00'))
        assert order_status(legacy) == order_status(canonical) == STATUS_PAID

    def test_sigue_coincidiendo_tras_cancelar(self, par):
        canonical, legacy = par
        canonical.action_cancel()
        legacy.refresh_from_db()
        assert order_status(legacy) == order_status(canonical) == STATUS_CANCELLED


class TestUnaVentaSinEspejoSeProyectaIgual:
    """El caso que E5 vuelve la norma: no hay fila espejo que desreferenciar."""

    def test_venta_sin_espejo_proyecta_su_estado(self, producto):
        venta = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, cart_token=uuid4())
        SaleOrderLine.objects.create(
            order=venta, product=producto, name=producto.name,
            product_uom_qty=1, price_unit=producto.price)
        venta.action_confirm()
        assert not hasattr(venta, 'legacy_order') or venta.legacy_order is None
        assert order_status(venta) == STATUS_PENDING

        Payment.objects.create(
            sale_order=venta, gateway=Payment.GATEWAY_MANUAL,
            status=Payment.STATUS_APPROVED, amount=Decimal('40.00'))
        assert order_status(venta) == STATUS_PAID
