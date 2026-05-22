"""
Celery tasks — apps.orders (UC-SYS-01).

cancel_timeout_orders: cancela ordenes PENDING con mas de
ORDER_PAYMENT_TIMEOUT_MINUTES minutos de antiguedad.
Se registra en Celery Beat (cada 5 min).
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import Order, OrderStatusLog

logger = logging.getLogger('apps')

ORDER_PAYMENT_TIMEOUT_MINUTES = 30


@shared_task(name='orders.cancel_timeout_orders')
def cancel_timeout_orders():
    """UC-SYS-01: cancela ordenes PENDING por timeout de pago."""
    cutoff = timezone.now() - timedelta(minutes=ORDER_PAYMENT_TIMEOUT_MINUTES)
    pending = Order.objects.filter(
        status=Order.STATUS_PENDING,
        created_at__lt=cutoff,
    )
    now = timezone.now()
    count = 0
    for order in pending.iterator():
        prev_status = order.status
        order.status             = Order.STATUS_CANCELLED_BY_TIMEOUT
        order.cancellation_reason = 'TIMEOUT'
        order.cancelled_at        = now
        order.save(update_fields=['status', 'cancellation_reason', 'cancelled_at'])
        OrderStatusLog.objects.create(
            order=order,
            previous_status=prev_status,
            new_status=Order.STATUS_CANCELLED_BY_TIMEOUT,
            changed_by=None,
            notes='Cancelacion automatica por timeout de pago.',
        )
        count += 1
    if count:
        logger.info('cancel_timeout_orders: %d ordenes canceladas.', count)
    return count
