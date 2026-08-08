"""Tests — V5c proyección del estado legacy (``analisis-unificar-orders-sale``).

``derive_order_status(sale_order)`` proyecta el enum legacy ``SaleOrder.status``
desde los ejes canónicos (sale.state / Payment / ShipmentGuide). El criterio
de correctitud del cut-over: la proyección **reproduce** el estado del espejo
``orders.Order`` en cada transición del ciclo de vida realmente alcanzable
(H-SALE-09). Prueba también que los estados legacy muertos no rompen la
proyección.

Post-E5 (retiro del addon espejo ``orders``, ``api@77bd1f0``): ``confirm_draft_order``
ya no devuelve un segundo objeto — la venta **es** la orden, y ``Payment``/
``ShipmentGuide`` sólo anclan por ``sale_order`` (el ``order`` de E4-pre se
retiró del todo, no sólo se volvió nullable). ``cancel_timeout_orders``
tampoco sobrevivió (0 hits en ``src/``, ver ``test_cancel_timeout_task.py``):
``TestCancelWritersMakeSaleAuthoritative.test_timeout_cancel_cancels_the_sale``
se retira por la misma razón que ese módulo.
"""
import uuid
from decimal import Decimal

import pytest

from addons.delivery.models import Courier, ShipmentGuide
from addons.sale.status_projection import (
    STATUS_CANCELLED,
    STATUS_DELIVERED,
    STATUS_DRAFT,
    STATUS_PAID,
    STATUS_PENDING,
    STATUS_SHIPPED,
    derive_order_status,
)
from addons.payment.models import Payment
from addons.sale.models import SaleOrder
from addons.sale.services import add_item_to_draft, cancel_order, confirm_draft_order
from tests.factories.product_factory import make_category, make_product

pytestmark = pytest.mark.django_db

ADDR = {
    'recipient_name': 'Test V5c', 'street': 'Calle 5c', 'city': 'CDMX',
    'state': 'CDMX', 'zip_code': '06600',
}


@pytest.fixture
def product_v5c(db):
    cat = make_category(name='Cat V5c')
    return make_product(name='Prod V5c', price=Decimal('110.00'), stock=7, categ=cat)


@pytest.fixture
def confirmed(product_v5c):
    """Confirma un draft y retorna la venta canónica confirmada."""
    draft = SaleOrder.objects.create(
        state=SaleOrder.STATE_DRAFT, cart_token=uuid.uuid4())
    add_item_to_draft(draft, product_v5c, quantity=1)
    confirm_draft_order(draft, address_data=dict(ADDR), guest_email='v5c@test.mx')
    draft.refresh_from_db()
    return draft


class TestProjectionFromCanonicalAxes:
    def test_draft_projects_draft(self, db):
        draft = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, cart_token=uuid.uuid4())
        assert derive_order_status(draft) == STATUS_DRAFT

    def test_pending_after_confirm(self, confirmed):
        assert derive_order_status(confirmed) == STATUS_PENDING

    def test_paid_after_payment_approved(self, confirmed):
        Payment.objects.create(
            sale_order=confirmed,
            gateway=Payment.GATEWAY_MERCADOPAGO,
            status=Payment.STATUS_APPROVED, amount=Decimal('110.00'))
        assert derive_order_status(confirmed) == STATUS_PAID

    def test_shipped_when_guide_created(self, confirmed):
        Payment.objects.create(
            sale_order=confirmed,
            gateway=Payment.GATEWAY_MERCADOPAGO,
            status=Payment.STATUS_APPROVED, amount=Decimal('110.00'))
        courier = Courier.objects.create(name='DHL V5c', code='DHL5C',)
        ShipmentGuide.objects.create(
            sale_order=confirmed, courier=courier,
            tracking_number='V5C-TRK-001')
        confirmed.refresh_from_db()
        assert derive_order_status(confirmed) == STATUS_SHIPPED

    def test_delivered_when_guide_delivered(self, confirmed):
        courier = Courier.objects.create(name='DHL V5c2', code='DHL5C2',)
        guide = ShipmentGuide.objects.create(
            sale_order=confirmed, courier=courier,
            tracking_number='V5C-TRK-002')
        guide.status = ShipmentGuide.STATUS_DELIVERED
        guide.save(update_fields=['status'])
        confirmed.refresh_from_db()
        assert derive_order_status(confirmed) == STATUS_DELIVERED

    def test_cancelled_when_sale_cancelled(self, confirmed):
        confirmed.action_cancel()
        confirmed.refresh_from_db()
        assert derive_order_status(confirmed) == STATUS_CANCELLED


class TestDeadGuideDoesNotShip:
    def test_cancelled_guide_falls_back_to_payment_axis(self, confirmed):
        Payment.objects.create(
            sale_order=confirmed,
            gateway=Payment.GATEWAY_MERCADOPAGO,
            status=Payment.STATUS_APPROVED, amount=Decimal('110.00'))
        courier = Courier.objects.create(name='DHL V5c3', code='DHL5C3',)
        guide = ShipmentGuide.objects.create(
            sale_order=confirmed, courier=courier,
            tracking_number='V5C-TRK-003')
        guide.status = ShipmentGuide.STATUS_CANCELLED
        guide.is_deleted = True
        guide.save(update_fields=['status', 'is_deleted'])
        confirmed.refresh_from_db()
        # Guía muerta → no cuenta como enviado; cae al eje de pago (PAID).
        assert derive_order_status(confirmed) == STATUS_PAID


class TestCancelWritersMakeSaleAuthoritative:
    """V5b-cancel (H-SALE-10): las rutas de cancelación deben cancelar la
    ``sale.order`` para que el eje comercial canónico (``sale.state``) sea
    autoritativo — de otro modo la proyección devuelve PENDING/PAID para una
    orden cancelada."""

    def test_manual_cancel_cancels_the_sale(self, confirmed):
        cancel_order(confirmed, reason='test V5b-cancel')
        confirmed.refresh_from_db()
        assert confirmed.state == SaleOrder.STATE_CANCEL
        assert derive_order_status(confirmed) == STATUS_CANCELLED
