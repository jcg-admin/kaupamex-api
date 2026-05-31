"""
Tests — UC-SYS-01: cancel_timeout_orders task.

Verifica que ordenes PENDING con mas de ORDER_PAYMENT_TIMEOUT_MINUTES
de antiguedad son canceladas con STATUS_CANCELLED_BY_TIMEOUT.
"""
import pytest
from datetime import timedelta
from django.utils import timezone
from apps.orders.models import Order, OrderStatusLog
from apps.orders.tasks import cancel_timeout_orders, ORDER_PAYMENT_TIMEOUT_MINUTES

pytestmark = pytest.mark.django_db


def _make_pending_order(age_minutes=ORDER_PAYMENT_TIMEOUT_MINUTES + 10):
    order = Order.objects.create(status=Order.STATUS_PENDING)
    Order.objects.filter(pk=order.pk).update(
        created_at=timezone.now() - timedelta(minutes=age_minutes)
    )
    order.refresh_from_db()
    return order


class TestCancelTimeoutOrders:

    def test_cancela_ordenes_pendientes_antiguas(self):
        order = _make_pending_order(age_minutes=ORDER_PAYMENT_TIMEOUT_MINUTES + 10)
        count = cancel_timeout_orders()
        order.refresh_from_db()
        assert order.status == Order.STATUS_CANCELLED_BY_TIMEOUT
        assert order.cancellation_reason == 'TIMEOUT'
        assert order.cancelled_at is not None
        assert count >= 1

    def test_respeta_ordenes_dentro_de_ventana(self):
        order = _make_pending_order(age_minutes=5)
        cancel_timeout_orders()
        order.refresh_from_db()
        assert order.status == Order.STATUS_PENDING

    def test_ignora_ordenes_no_pending(self):
        order = _make_pending_order(age_minutes=ORDER_PAYMENT_TIMEOUT_MINUTES + 10)
        Order.objects.filter(pk=order.pk).update(status=Order.STATUS_PROCESSING)
        order.refresh_from_db()
        cancel_timeout_orders()
        order.refresh_from_db()
        assert order.status == Order.STATUS_PROCESSING

    def test_crea_status_log(self):
        order = _make_pending_order(age_minutes=ORDER_PAYMENT_TIMEOUT_MINUTES + 10)
        cancel_timeout_orders()
        log = OrderStatusLog.objects.filter(order=order).first()
        assert log is not None
        assert log.previous_status == Order.STATUS_PENDING
        assert log.new_status == Order.STATUS_CANCELLED_BY_TIMEOUT
        assert log.changed_by is None
