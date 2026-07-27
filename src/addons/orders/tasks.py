"""
Tareas periodicas de sistema — addons.orders (UC-SYS-01).

cancel_timeout_orders: cancela ordenes PENDING con mas de
ORDER_PAYMENT_TIMEOUT_MINUTES minutos de antiguedad.
Invocada por management command cancel_timeout_orders (cron cada 5 min).
"""
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from addons.inventory.services import InventoryService
from .models import Order, OrderStatusLog
from .status_projection import order_status, filter_orders_by_status

logger = logging.getLogger('apps')

ORDER_PAYMENT_TIMEOUT_MINUTES = 30


def cancel_timeout_orders():
    """UC-SYS-01: cancela ordenes PENDING por timeout de pago."""
    cutoff = timezone.now() - timedelta(minutes=ORDER_PAYMENT_TIMEOUT_MINUTES)
    # Collect IDs first; iterate outside any lock.
    # O2C R8-pre (H-API-18): el PENDING se deriva de los ejes canónicos
    # (venta confirmada, sin pago aprobado, sin guía) vía
    # ``filter_orders_by_status`` — null-safe para filas legacy — en vez de
    # leer la columna espejo ``status=PENDING`` directamente.
    pending_ids = list(
        filter_orders_by_status(Order.objects.all(), Order.STATUS_PENDING)
        .filter(created_at__lt=cutoff)
        .values_list('id', flat=True)
    )
    now = timezone.now()
    count = 0
    for order_id in pending_ids:
        # H-TASKS-01: re-verificar bajo lock para evitar sobreescribir
        # una orden que ya transitó a PAID (pago llegó después del query).
        with transaction.atomic():
            order = (
                Order.objects.select_for_update()
                .select_related('sale_order')
                .filter(pk=order_id)
                .first()
            )
            # Re-derivar el estado canónico bajo lock: si el pago llegó entre
            # el query y el lock, la orden ya no proyecta PENDING → se salta.
            if order is None or order_status(order) != Order.STATUS_PENDING:
                continue
            # O2C R8: el estado lo fija el EJE comercial (action_cancel); la
            # columna espejo ya no se escribe (V5d la retira). El sub-eje
            # "por timeout" se preserva en cancellation_reason='TIMEOUT'.
            order.cancellation_reason = 'TIMEOUT'
            order.cancelled_at        = now
            order.save(update_fields=['cancellation_reason', 'cancelled_at', 'updated_at'])

            # V5b-cancel (H-SALE-10): la cancelación por timeout también
            # cancela la sale.order canónica (eje comercial autoritativo).
            sale = order.sale_order
            if sale is not None and sale.state != sale.STATE_CANCEL and not sale.locked:
                sale.action_cancel()
            OrderStatusLog.objects.create(
                order=order,
                previous_status=Order.STATUS_PENDING,
                new_status=Order.STATUS_CANCELLED_BY_TIMEOUT,
                changed_by=None,
                notes='Cancelacion automatica por timeout de pago.',
            )

            # UC-SYS-01 POST-02 / BR-016: el stock se decrementa al crear la
            # orden (checkout), asi que una cancelacion por timeout DEBE
            # restaurarlo — simetrico con la cancelacion manual (UC-ORD-04).
            # restore es idempotente por (reference=order_number, product,
            # variant), evitando doble restauracion.
            stock_items = [
                {'product': item.product,
                 'variant': item.variant,
                 'quantity': item.quantity}
                for item in order.items.select_related('product', 'variant').all()
                if item.product
            ]
            if stock_items:
                InventoryService.restore(
                    items=stock_items,
                    reference=order.order_number,
                    created_by=None,
                )
                logger.info(
                    'cancel_timeout_orders: stock restaurado orden %s (%d items).',
                    order.order_number, len(stock_items),
                )
            count += 1
    if count:
        logger.info('cancel_timeout_orders: %d ordenes canceladas.', count)
    return count
