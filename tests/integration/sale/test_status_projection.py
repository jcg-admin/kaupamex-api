"""Tests — V5c proyección del estado legacy (``analisis-unificar-orders-sale``).

``derive_order_status(sale_order)`` proyecta el enum legacy ``Order.status``
desde los ejes canónicos (sale.state / Payment / ShipmentGuide). El criterio
de correctitud del cut-over: la proyección **reproduce** el estado del espejo
``orders.Order`` en cada transición del ciclo de vida realmente alcanzable
(H-SALE-09). Prueba también que los estados legacy muertos no rompen la
proyección.
"""
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest

from django.utils import timezone

from addons.catalogue.models import Category, Product
from addons.delivery.models import Courier, ShipmentGuide
from addons.orders.models import Order
from addons.orders.services import cancel_order
from addons.sale.status_projection import (
    STATUS_CANCELLED,
    STATUS_DELIVERED,
    STATUS_DRAFT,
    STATUS_PAID,
    STATUS_PENDING,
    STATUS_SHIPPED,
    derive_order_status,
)
from addons.orders.tasks import cancel_timeout_orders
from addons.payment.models import Payment
from addons.sale.models import SaleOrder
from addons.sale.services import add_item_to_draft, confirm_draft_order

pytestmark = pytest.mark.django_db

ADDR = {
    'recipient_name': 'Test V5c', 'street': 'Calle 5c', 'city': 'CDMX',
    'state': 'CDMX', 'zip_code': '06600',
}


@pytest.fixture
def product_v5c(db):
    cat = Category.objects.create(name='Cat V5c', slug='cat-v5c', is_active=True)
    p = Product.objects.create(
        name='Prod V5c', slug='prod-v5c', sku='V5C-001', description='',
        price=Decimal('110.00'), stock=7, is_active=True, is_published=True,
    )
    p.categories.add(cat)
    return p


@pytest.fixture
def confirmed(product_v5c):
    """Confirma un draft y retorna (canónica sale, espejo legacy)."""
    draft = SaleOrder.objects.create(
        state=SaleOrder.STATE_DRAFT, cart_token=uuid.uuid4())
    add_item_to_draft(draft, product_v5c, quantity=1)
    legacy = confirm_draft_order(draft, address_data=dict(ADDR),
                                 guest_email='v5c@test.mx')
    draft.refresh_from_db()
    return draft, legacy


class TestProjectionFromCanonicalAxes:
    def test_draft_projects_draft(self, db):
        draft = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, cart_token=uuid.uuid4())
        assert derive_order_status(draft) == STATUS_DRAFT

    def test_pending_after_confirm(self, confirmed):
        sale, _legacy = confirmed
        assert derive_order_status(sale) == STATUS_PENDING

    def test_paid_after_payment_approved(self, confirmed):
        sale, legacy = confirmed
        Payment.objects.create(
            order=legacy, sale_order=sale,
            gateway=Payment.GATEWAY_MERCADOPAGO,
            status=Payment.STATUS_APPROVED, amount=Decimal('110.00'))
        # O2C V5d: la columna espejo fue retirada — ya no hay un
        # ``legacy.status`` contra el cual contrastar; el eje ES el estado.
        assert derive_order_status(sale) == STATUS_PAID

    def test_shipped_when_guide_created(self, confirmed):
        sale, legacy = confirmed
        Payment.objects.create(
            order=legacy, sale_order=sale,
            gateway=Payment.GATEWAY_MERCADOPAGO,
            status=Payment.STATUS_APPROVED, amount=Decimal('110.00'))
        courier = Courier.objects.create(name='DHL V5c', code='DHL5C',
                                         is_active=True)
        ShipmentGuide.objects.create(
            order=legacy, sale_order=sale, courier=courier,
            tracking_number='V5C-TRK-001')
        # O2C V5d: sin espejo que escribir; la guia viva ES el eje.
        sale.refresh_from_db()
        assert derive_order_status(sale) == STATUS_SHIPPED

    def test_delivered_when_guide_delivered(self, confirmed):
        sale, legacy = confirmed
        courier = Courier.objects.create(name='DHL V5c2', code='DHL5C2',
                                         is_active=True)
        guide = ShipmentGuide.objects.create(
            order=legacy, sale_order=sale, courier=courier,
            tracking_number='V5C-TRK-002')
        guide.status = ShipmentGuide.STATUS_DELIVERED
        guide.save(update_fields=['status'])
        sale.refresh_from_db()
        assert derive_order_status(sale) == STATUS_DELIVERED

    def test_cancelled_when_sale_cancelled(self, confirmed):
        sale, legacy = confirmed
        sale.action_cancel()
        sale.refresh_from_db()
        assert derive_order_status(sale) == STATUS_CANCELLED


class TestDeadGuideDoesNotShip:
    def test_cancelled_guide_falls_back_to_payment_axis(self, confirmed):
        sale, legacy = confirmed
        Payment.objects.create(
            order=legacy, sale_order=sale,
            gateway=Payment.GATEWAY_MERCADOPAGO,
            status=Payment.STATUS_APPROVED, amount=Decimal('110.00'))
        courier = Courier.objects.create(name='DHL V5c3', code='DHL5C3',
                                         is_active=True)
        guide = ShipmentGuide.objects.create(
            order=legacy, sale_order=sale, courier=courier,
            tracking_number='V5C-TRK-003')
        guide.status = ShipmentGuide.STATUS_CANCELLED
        guide.is_deleted = True
        guide.save(update_fields=['status', 'is_deleted'])
        sale.refresh_from_db()
        # Guía muerta → no cuenta como enviado; cae al eje de pago (PAID).
        assert derive_order_status(sale) == STATUS_PAID


class TestCancelWritersMakeSaleAuthoritative:
    """V5b-cancel (H-SALE-10): las rutas de cancelación deben cancelar la
    ``sale.order`` para que el eje comercial canónico (``sale.state``) sea
    autoritativo — de otro modo la proyección devuelve PENDING/PAID para una
    orden cancelada."""

    def test_manual_cancel_cancels_the_sale(self, confirmed):
        sale, legacy = confirmed
        cancel_order(legacy, reason='test V5b-cancel')
        sale.refresh_from_db()
        legacy.refresh_from_db()
        # O2C R8: la columna espejo ya no se escribe — el estado es la
        # proyección del eje comercial (sale.state).
        assert sale.state == SaleOrder.STATE_CANCEL
        assert derive_order_status(sale) == STATUS_CANCELLED

    def test_timeout_cancel_cancels_the_sale(self, confirmed):
        sale, legacy = confirmed
        # La tarea escanea órdenes PENDING con created_at anterior al cutoff.
        Order.objects.filter(pk=legacy.pk).update(
            created_at=timezone.now() - timedelta(hours=2))
        cancel_timeout_orders()
        sale.refresh_from_db()
        legacy.refresh_from_db()
        # O2C R8: el sub-eje "por timeout" vive en cancellation_reason; el
        # estado es la proyección del eje comercial (sale.state).
        assert legacy.cancellation_reason == 'TIMEOUT'
        assert sale.state == SaleOrder.STATE_CANCEL
        assert derive_order_status(sale) == STATUS_CANCELLED
