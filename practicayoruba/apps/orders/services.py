"""
OrderService — apps.orders
Sprint 18 — UC-ORD-04, UC-ORD-05, UC-ORD-06

Orquesta cancelación, edición de dirección y cambio de método de envío.
Centraliza la lógica de negocio fuera de las vistas.
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.inventory.services import InventoryService
from apps.inventory.proxy_models import CancellationMovement
from .models import OrderAddress
from apps.payments.services import execute_refund
from apps.settings_app.models import ShippingMethod


logger = logging.getLogger('apps')

# ─── Estados que permiten cada operación ────────────────────────────────────
# H-ORD-002: mapeo FR→modelo (PENDING_PAYMENT→PENDING, PAYMENT_CONFIRMED→PROCESSING)
# H-ORD-S01: PAGADA debe incluirse — pago confirmado pero aún no en preparación.
CANCELABLE_STATUSES = ['PENDING', 'PROCESSING', 'PAGADA']
EDITABLE_STATUSES   = ['PENDING', 'PROCESSING', 'PAGADA', 'IN_PREPARATION']  # dirección y envío


def cancel_order(order, reason: str = '', cancelled_by=None, cancelable_statuses=None):
    """
    Cancela una orden de forma atómica.
    UC-ORD-04 (FR-ORD-04.02, FR-ORD-04.03).

    Pasos en una sola transacción:
      1. Valida que el estado sea cancelable
      2. Cambia Order.status → CANCELLED + registra campos de cancelación
      3. Restaura el stock de cada OrderItem (InventoryService.restore)
      4. Inicia el reembolso si hay Payment aprobado (execute_refund)

    :raises ValueError: si la orden no es cancelable
    :raises RuntimeError: si el gateway de reembolso falla
    """

    _cancelable = cancelable_statuses if cancelable_statuses is not None else CANCELABLE_STATUSES
    if order.status not in _cancelable:
        raise ValueError(
            f'La orden {order.order_number} no se puede cancelar '
            f'(estado: {order.status}). Solo se permiten cancelaciones '
            f'en estados: {_cancelable}.'
        )

    with transaction.atomic():
        # H-API-35: re-verificar el estado bajo lock para prevenir
        # que dos cancelaciones concurrentes restauren el stock dos veces.
        if not Order.objects.select_for_update().filter(
            pk=order.pk, status__in=_cancelable
        ).exists():
            raise ValueError(
                f'La orden {order.order_number} ya no es cancelable '
                f'(cancelada por request concurrente).'
            )

        # 1. Cancelar la orden
        order.status              = 'CANCELLED'
        order.cancellation_reason = reason
        order.cancelled_at        = timezone.now()
        order.save(update_fields=['status', 'cancellation_reason', 'cancelled_at'])

        # 2. Restaurar stock — UC-INV-03
        stock_items = [
            {
                'product':  item.product if item.product else None,
                'variant':  item.variant,
                'quantity': item.quantity,
            }
            for item in order.items.select_related('product', 'variant').all()
            if item.product  # seguridad: product puede ser null si fue eliminado
        ]
        if stock_items:
            InventoryService.restore(
                items=stock_items,
                reference=order.order_number,
                created_by=cancelled_by,
            )
            logger.info(
                'Stock restaurado para orden cancelada %s — %d items',
                order.order_number, len(stock_items),
            )

        # 3. Reembolso si había pago aprobado — H-ORD-004 / H-REF-005
        approved_payment = (
            order.payments.filter(status='APPROVED').order_by('-created_at').first()
        )
        if approved_payment:
            try:
                refund = execute_refund(
                    payment=approved_payment,
                    amount=None,  # reembolso total
                    reason=f'Cancelación de orden {order.order_number}: {reason}',
                    initiated_by=cancelled_by,
                )
                logger.info(
                    'Reembolso iniciado para orden cancelada %s — refund_id=%s',
                    order.order_number, refund.gateway_refund_id,
                )
            except RuntimeError as exc:
                # El gateway falló — hacemos rollback de toda la transacción
                logger.error(
                    'Cancelación abortada para %s — fallo del gateway: %s',
                    order.order_number, exc,
                )
                raise

    return order


def update_order_address(order, address_data: dict):
    """
    Actualiza la dirección de entrega de una orden.
    UC-ORD-05 (FR-ORD-05.02).

    Solo posible en estados: PENDING, PROCESSING, IN_PREPARATION.
    :raises ValueError: si la orden no permite editar la dirección.
    """

    if order.status not in EDITABLE_STATUSES:
        raise ValueError(
            f'La orden {order.order_number} no permite editar la dirección '
            f'(estado: {order.status}). La guía de envío ya fue creada.'
        )

    try:
        address = order.address
    except OrderAddress.DoesNotExist:
        address = OrderAddress(order=order)

    for field, value in address_data.items():
        setattr(address, field, value)
    address.save()

    logger.info('Dirección actualizada para orden %s', order.order_number)
    return address


class OrderNotEditableError(ValueError):
    """UC-ORD-06: la orden no permite cambios (estado no editable)."""


class ShippingMethodNotAvailableError(ValueError):
    """UC-ORD-06: el shipping_method indicado no existe o esta inactivo."""


def update_shipping_method(order, shipping_method_id: int):
    """
    Cambia el método de envío y recalcula el total.
    UC-ORD-06 (FR-ORD-06.02) v2.1.0 (DEC-ORD-04).

    Solo posible en estados: PENDING, PROCESSING, IN_PREPARATION.
    Recalcula: OrderValue.shipping_cost y OrderValue.total.

    :raises OrderNotEditableError: si la orden no permite cambiar el envío.
    :raises ShippingMethodNotAvailableError: si el método no existe o está inactivo.
    """

    if order.status not in EDITABLE_STATUSES:
        raise OrderNotEditableError(
            f'La orden {order.order_number} no permite cambiar el método '
            f'de envío (estado: {order.status}).'
        )

    try:
        new_method = ShippingMethod.objects.get(pk=shipping_method_id, is_active=True)
    except ShippingMethod.DoesNotExist:
        raise ShippingMethodNotAvailableError(
            f'El método de envío {shipping_method_id} no existe o está inactivo.'
        )

    with transaction.atomic():
        value = order.value
        neto  = value.subtotal - value.discount

        # Verificar si aplica envío gratis
        if (new_method.free_threshold is not None
                and neto >= new_method.free_threshold):
            new_shipping_cost = Decimal('0.00')
        else:
            new_shipping_cost = new_method.cost

        # H-ORD-007: total = subtotal_neto + tax + shipping
        value.shipping_cost = new_shipping_cost
        value.total         = neto + value.tax + new_shipping_cost
        value.save(update_fields=['shipping_cost', 'total'])

        order.shipping_method = new_method
        order.save(update_fields=['shipping_method'])

    logger.info(
        'Método de envío actualizado para orden %s → %s ($%s)',
        order.order_number, new_method.name, new_shipping_cost,
    )
    return order
