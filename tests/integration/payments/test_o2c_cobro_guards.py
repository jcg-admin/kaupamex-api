"""Tests — guards de lectura de cobro sobre ejes canónicos O2C (Rebanada 3).

Cut-over ``orders → sale`` (ADR-024, #205). Los lectores de la capa de cobro
(``payments/services.py`` + ``serializers.py``) dejan de leer la columna espejo
``orders_order.status`` (retirada en V5d) y derivan el estado desde los ejes
canónicos vía ``sale.status_projection.order_status`` (sale.state + Payment +
guía). Estos tests prueban que el guard sigue la **proyección**, no la columna:
una orden con la columna espejo *stale* respecto a los ejes debe evaluarse por
los ejes.
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from addons.payment.models import Payment
from addons.payments.serializers import AdminPaymentSerializer
from addons.payments.services import get_payment_status, get_retry_eligibility
from addons.sale.models import SaleOrder
from addons.sale.status_projection import (
    STATUS_PAID,
    STATUS_PENDING,
)

pytestmark = pytest.mark.integration

User = get_user_model()


def _make_user(email='cobro-o2c@example.com'):
    return User.objects.create_user(email=email, password='x')


def _canonical_order(user, *, approved, mirror_status):
    """Orden enlazada a una SaleOrder confirmada, con columna espejo *stale*.

    :param approved: si True, añade un Payment APPROVED (proyecta PAID);
                     si False, sin pago aprobado (proyecta PENDING).
    :param mirror_status: valor deliberadamente *stale* de ``order.status``
                          para probar que el guard NO lo lee.
    """
    so = SaleOrder.objects.create(state=SaleOrder.STATE_SALE)
    order = SaleOrder.objects.create(user=user, sale_order=so)
    if approved:
        Payment.objects.create(
            order=order, sale_order=so,
            gateway=Payment.GATEWAY_MERCADOPAGO,
            amount=Decimal('580.00'),
            status=Payment.STATUS_APPROVED,
        )
    return order


@pytest.mark.django_db
class TestRetryEligibilityOnProjection:
    """``get_retry_eligibility`` (services.py:346) lee la proyección."""

    def test_eligible_when_canonical_pending_despite_stale_paid_column(self):
        # Ejes: sale='sale' + sin pago aprobado → proyección PENDING.
        # Columna espejo mentida a PAID: el guard NO debe leerla.
        user = _make_user('retry-pending@example.com')
        order = _canonical_order(user, approved=False, mirror_status=STATUS_PAID)

        result = get_retry_eligibility(order.order_number, user)

        assert result is not None
        assert result['eligible'] is True
        assert result['order_status'] == STATUS_PENDING

    def test_not_eligible_when_canonical_paid_despite_stale_pending_column(self):
        # Ejes: sale='sale' + pago aprobado → proyección PAID.
        # Columna espejo mentida a PENDING: el guard debe rechazar por eje.
        user = _make_user('retry-paid@example.com')
        order = _canonical_order(user, approved=True, mirror_status=STATUS_PENDING)

        result = get_retry_eligibility(order.order_number, user)

        assert result is not None
        assert result['eligible'] is False
        assert result['codigo_error'] == 'ORDER_NOT_RETRYABLE'
        # El motivo cita el estado proyectado (PAID), no la columna (PENDING).
        assert STATUS_PAID in result['reason']


@pytest.mark.django_db
class TestPaymentStatusDisplayOnProjection:
    """``get_payment_status`` (services.py:301) expone el estado proyectado."""

    def test_order_status_is_projected_not_column(self):
        user = _make_user('status-disp@example.com')
        # Ejes → PAID; columna espejo stale → PENDING.
        order = _canonical_order(user, approved=True, mirror_status=STATUS_PENDING)

        payload = get_payment_status(order.order_number, user)

        assert payload['order_status'] == STATUS_PAID


@pytest.mark.django_db
class TestAdminSerializerOrderStatusOnProjection:
    """``AdminPaymentSerializer.order_status`` deriva de la proyección."""

    def test_serializer_order_status_from_axes_not_column(self):
        user = _make_user('admin-ser@example.com')
        order = _canonical_order(user, approved=True, mirror_status=STATUS_PENDING)
        payment = order.payments.first()

        data = AdminPaymentSerializer(payment).data

        assert data['order_status'] == STATUS_PAID

    def test_serializer_order_status_pending_without_approved_payment(self):
        user = _make_user('admin-ser2@example.com')
        # Sin pago aprobado → PENDING; pero necesitamos un Payment (no aprobado)
        # para serializar: lo creamos FAILED, que no altera la proyección.
        so = SaleOrder.objects.create(state=SaleOrder.STATE_SALE)
        order = SaleOrder.objects.create(user=user, sale_order=so)
        payment = Payment.objects.create(
            order=order, sale_order=so,
            gateway=Payment.GATEWAY_MERCADOPAGO,
            amount=Decimal('100.00'),
            status=Payment.STATUS_FAILED,
        )

        data = AdminPaymentSerializer(payment).data

        assert data['order_status'] == STATUS_PENDING
