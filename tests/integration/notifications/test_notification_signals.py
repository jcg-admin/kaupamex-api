"""
Tests — Signal wiring para notificaciones transaccionales (UC-NOT-01..05)

Verifica que los signal receivers en addons.mail.models.notification_signals disparan
las funciones notify_* correctas cuando los modelos de dominio cambian.

on_commit se parchea para ejecutar callbacks inmediatamente (los tests
corren en transacciones que nunca commitean).
"""
import pytest
from decimal import Decimal
from unittest.mock import patch

from addons.mail.models import Notification
from addons.mail.models.notification_service import notify_order_status_changed
from addons.orders.models import Order, OrderValue
from addons.payment.models import Payment, Refund
from addons.stock.models import ReturnRequest
from tests.factories.order_factory import make_order

pytestmark = pytest.mark.integration

_ON_COMMIT_PATH = 'addons.mail.models.notification_service.transaction.on_commit'


# ── Helpers ─────────────────────────────────────────────────────────────

def _make_order(user):
    return make_order(user=user)


def _make_order_value(order, total=Decimal('464.00')):
    return OrderValue.objects.create(
        order=order,
        subtotal=Decimal('400.00'),
        tax=Decimal('64.00'),
        shipping_cost=Decimal('0.00'),
        discount=Decimal('0.00'),
        total=total,
    )


def _make_payment(order):
    return Payment.objects.create(
        order=order,
        sale_order=order.sale_order,
        gateway=Payment.GATEWAY_MERCADOPAGO,
        gateway_payment_id=None,
        amount=Decimal('464.00'),
        status=Payment.STATUS_APPROVED,
    )


# ── UC-NOT-01: OrderValue created triggers order confirmation ─────────────

class TestOrderCreatedSignal:
    def test_creates_notification_on_order_value_save(self, db, user):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            order = _make_order(user)
            _make_order_value(order)

        assert Notification.objects.filter(
            user=user,
            type='ORDER_UPDATE',
        ).exists()

    def test_notification_contains_order_number(self, db, user):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            order = _make_order(user)
            _make_order_value(order)

        notif = Notification.objects.filter(user=user, type='ORDER_UPDATE').first()
        assert order.order_number in notif.subject

    def test_no_notification_if_user_is_none(self, db):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            order = make_order(user=None)
            _make_order_value(order)

        assert not Notification.objects.filter(type='ORDER_UPDATE').exists()

    def test_no_duplicate_on_order_value_update(self, db, user):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            order = _make_order(user)
            ov = _make_order_value(order)
            ov.total = Decimal('500.00')
            ov.save(update_fields=['total'])

        assert Notification.objects.filter(user=user, type='ORDER_UPDATE').count() == 1


# ── UC-NOT-02: notificacion EXPLICITA por transicion de eje (O2C V5d) ─────
#
# La signal ``post_save`` que observaba ``Order.status`` murio con la columna
# espejo (V5d, H-API-20): sin campo no hay cambio que observar. El mecanismo
# vigente es la llamada explicita ``notify_order_status_changed`` en cada punto
# de mutacion del eje (hub admin, cancel_order, alta de guia, entrega). Estos
# tests ejercen ese contrato directamente.

class TestOrderStatusChangedNotification:
    def test_creates_notification_on_status_transition(self, db, user):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            order = _make_order(user)
            notify_order_status_changed(order, Order.STATUS_SHIPPED)

        assert Notification.objects.filter(
            user=user,
            type='ORDER_UPDATE',
        ).exists()

    def test_no_notification_for_non_notified_status(self, db, user):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            order = _make_order(user)
            initial_count = Notification.objects.filter(user=user).count()
            # PENDING no esta en el conjunto notificable
            notify_order_status_changed(order, Order.STATUS_PENDING)

        assert Notification.objects.filter(user=user).count() == initial_count

    def test_no_notification_on_order_creation(self, db, user):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            _make_order(user)

        assert not Notification.objects.filter(
            user=user,
            subject__icontains='cambio',
        ).exists()

    def test_shipped_notification_has_correct_subject(self, db, user):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            order = _make_order(user)
            notify_order_status_changed(order, Order.STATUS_SHIPPED)

        notif = Notification.objects.filter(user=user, type='ORDER_UPDATE').first()
        assert 'enviado' in notif.subject.lower()


# ── UC-NOT-04: ReturnRequest status transition ───────────────────────────

class TestReturnStatusChangedSignal:
    def _make_return(self, user, order):
        return ReturnRequest.objects.create(
            user=user,
            order_id=order.pk,
            reason=ReturnRequest.Reason.DAMAGED_PRODUCT,
            description='Producto llego roto en el empaque.',
            status=ReturnRequest.Status.PENDING_REVIEW,
        )

    def test_creates_notification_on_approval(self, db, user):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            order = _make_order(user)
            ret = self._make_return(user, order)
            ret.status = ReturnRequest.Status.APPROVED
            ret.save(update_fields=['status', 'updated_at'])

        assert Notification.objects.filter(
            user=user,
            type='RETURN_UPDATE',
        ).exists()

    def test_creates_notification_on_rejection(self, db, user):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            order = _make_order(user)
            ret = self._make_return(user, order)
            ret.rejection_reason = 'Fuera de periodo de devolucion.'
            ret.status = ReturnRequest.Status.REJECTED
            ret.save(update_fields=['status', 'rejection_reason', 'updated_at'])

        assert Notification.objects.filter(
            user=user,
            type='RETURN_UPDATE',
        ).exists()

    def test_no_notification_on_non_terminal_status(self, db, user):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            order = _make_order(user)
            ret = self._make_return(user, order)
            ret.status = ReturnRequest.Status.INFO_REQUESTED
            ret.save(update_fields=['status', 'updated_at'])

        assert not Notification.objects.filter(user=user, type='RETURN_UPDATE').exists()

    def test_no_notification_on_return_creation(self, db, user):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            order = _make_order(user)
            self._make_return(user, order)

        assert not Notification.objects.filter(user=user, type='RETURN_UPDATE').exists()


# ── UC-NOT-05: Refund created ──────────────────────────────────────────────

class TestRefundCreatedSignal:
    def test_creates_notification_on_approved_refund(self, db, user):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            order = _make_order(user)
            payment = _make_payment(order)
            Refund.objects.create(
                payment=payment,
                amount=Decimal('464.00'),
                status=Refund.STATUS_APPROVED,
            )

        assert Notification.objects.filter(
            user=user,
            type='RETURN_UPDATE',
        ).exists()

    def test_no_notification_on_pending_refund(self, db, user):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            order = _make_order(user)
            payment = _make_payment(order)
            Refund.objects.create(
                payment=payment,
                amount=Decimal('464.00'),
                status=Refund.STATUS_PENDING,
            )

        assert not Notification.objects.filter(user=user, type='RETURN_UPDATE').exists()
