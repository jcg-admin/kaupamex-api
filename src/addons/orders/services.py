"""
OrderService — addons.orders
Sprint 18 — UC-ORD-04, UC-ORD-05, UC-ORD-06

Orquesta cancelación, edición de dirección y cambio de método de envío.
Centraliza la lógica de negocio fuera de las vistas.
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from addons.inventory.services import InventoryService
from .models import Order, OrderAddress, OrderStatusLog
from .status_projection import order_status
from addons.mail.models.notification_service import notify_order_status_changed
from addons.payments.services import execute_refund
from addons.delivery.models import ShippingMethod


logger = logging.getLogger('apps')

# ─── Estados que permiten cada operación ────────────────────────────────────
# O2C R8-pre (H-API-17): vocabulario canónico de 6 valores. Los guards leen el
# estado vía ``order_status(order)`` (proyección null-safe: ejes O2C para filas
# con ``sale_order``, columna espejo para filas legacy pre-V3a), NO ``.status``
# directo — así estos consumidores dejan de atar el cancelar/editar a la columna
# espejo (preparación para su retiro en V5d). PROCESSING/IN_PREPARATION eran
# valores MUERTOS (0 escritores; la proyección nunca los emite).
CANCELABLE_STATUSES = ['PENDING', 'PAID']
EDITABLE_STATUSES   = ['PENDING', 'PAID']  # dirección de envío
# D-3 (UC-ORD-06): cambiar el método de envío recalcula el total; en una orden
# ya pagada (PAID) eso deja el pago capturado sin conciliar (cobro/reembolso de
# la diferencia no implementado). Se restringe a PRE-pago (PENDING), de modo que
# el recálculo siempre precede a la captura del pago.
SHIPPING_METHOD_EDITABLE_STATUSES = ['PENDING']


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
    if order_status(order) not in _cancelable:
        raise ValueError(
            f'La orden {order.order_number} no se puede cancelar '
            f'(estado: {order_status(order)}). Solo se permiten cancelaciones '
            f'en estados: {_cancelable}.'
        )

    with transaction.atomic():
        # H-API-35 / O2C R8-pre (H-API-17): re-verificar el estado bajo lock
        # para prevenir que dos cancelaciones concurrentes restauren el stock
        # dos veces.  Se bloquea la fila y se re-deriva el estado canónico con
        # ``order_status`` (no la columna espejo); se opera sobre la instancia
        # bloqueada.
        order = (
            Order.objects.select_for_update()
            .select_related('sale_order')
            .get(pk=order.pk)
        )
        if order_status(order) not in _cancelable:
            raise ValueError(
                f'La orden {order.order_number} ya no es cancelable '
                f'(cancelada por request concurrente).'
            )

        # 1. Cancelar la orden — O2C R8: el estado lo fija el EJE comercial
        # (sale.action_cancel); la columna espejo ya no se escribe (V5d la
        # retira). Los campos de metadata de cancelación sí son de la orden.
        previous_status           = order_status(order)
        order.cancellation_reason = reason
        order.cancelled_at        = timezone.now()
        order.save(update_fields=['cancellation_reason', 'cancelled_at', 'updated_at'])

        # V5b-cancel (H-SALE-10): cancelar la sale.order canónica — el eje
        # comercial (sale.state) es autoritativo; la proyección deriva
        # CANCELLED de él.
        sale = order.sale_order
        if sale is not None and sale.state != sale.STATE_CANCEL and not sale.locked:
            sale.action_cancel()

        # Registrar transición en el log de auditoría — UC-ORD-04
        OrderStatusLog.objects.create(
            order=order,
            previous_status=previous_status,
            new_status='CANCELLED',
            changed_by=cancelled_by,
            notes=reason,
        )

        # UC-NOT-02 (O2C R8): sin escritura de la columna espejo la signal
        # post_save ya no dispara — notificación explícita en el punto de
        # transición del eje.
        notify_order_status_changed(order, 'CANCELLED')

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
        # O2C R8: los pagos conciliados a mano (gateway MANUAL, UC-ORD-07)
        # no tienen pasarela a la cual pedir el reembolso — su devolución es
        # un proceso manual fuera de la plataforma. Se excluyen del refund
        # automático (get_gateway('MANUAL') no existe y abortaría el cancel).
        approved_payment = (
            order.payments.filter(status='APPROVED')
            .exclude(gateway='MANUAL')
            .order_by('-created_at').first()
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


def _format_address(address) -> str:
    return f'{address.street}, {address.city}, {address.state} {address.zip_code}'


def update_order_address(order, address_data: dict, changed_by=None):
    """
    Actualiza la dirección de entrega de una orden.
    UC-ORD-05 (FR-ORD-05.02).

    Solo posible en estados: PENDING, PROCESSING, IN_PREPARATION.

    H-API-05: deja un registro de auditoría (OrderStatusLog) por cada
    edición, siguiendo el mismo patrón que cancel_order — sin transición
    real de Order.status (previous_status == new_status), porque editar
    la dirección no cambia el estado de la orden.

    :raises ValueError: si la orden no permite editar la dirección.
    """

    if order_status(order) not in EDITABLE_STATUSES:
        raise ValueError(
            f'La orden {order.order_number} no permite editar la dirección '
            f'(estado: {order_status(order)}). La guía de envío ya fue creada.'
        )

    try:
        address = order.address
        previous_summary = _format_address(address)
    except OrderAddress.DoesNotExist:
        address = OrderAddress(order=order)
        previous_summary = '(sin dirección previa)'

    for field, value in address_data.items():
        setattr(address, field, value)
    address.save()

    OrderStatusLog.objects.create(
        order=order,
        previous_status=order.status,
        new_status=order.status,
        changed_by=changed_by,
        notes=(
            f'Dirección actualizada: {previous_summary} → '
            f'{_format_address(address)}'
        ),
    )

    logger.info('Dirección actualizada para orden %s', order.order_number)
    return address


class OrderNotEditableError(ValueError):
    """UC-ORD-06: la orden no permite cambios (estado no editable)."""


class ShippingMethodNotAvailableError(ValueError):
    """UC-ORD-06: el shipping_method indicado no existe o esta inactivo."""


def update_shipping_method(order, shipping_method_id: int, changed_by=None):
    """
    Cambia el método de envío y recalcula el total.
    UC-ORD-06 (FR-ORD-06.02) v2.2.0 (DEC-ORD-04).

    DEPRECADO (2026-07-07): el comprador ya no elige método de envío (el envío
    se deriva por zona, GRATIS open-closed; supersede DEC-BC-19/DEC-BC-25). Se
    conserva el servicio marcado deprecado; su retiro efectivo queda para una
    iniciativa dedicada.

    Solo posible en estados PRE-pago: PENDING, PROCESSING
    (SHIPPING_METHOD_EDITABLE_STATUSES). Recalcula OrderValue.shipping_cost
    y OrderValue.total.

    H-API-06: deja un registro de auditoría (OrderStatusLog) por cada
    cambio, siguiendo el mismo patrón que cancel_order — sin transición
    real de Order.status (previous_status == new_status).

    D-3 (resuelto — rechazar post-pago): en una orden PAID/IN_PREPARATION
    el pago ya está capturado; recalcular el total sin cobrar/reembolsar la
    diferencia dejaría el pago sin conciliar. Por eso el cambio se rechaza
    con OrderNotEditableError en esos estados. La conciliación automática
    (cobro/reembolso vía pasarela) sería una sub-iniciativa futura.

    :raises OrderNotEditableError: si la orden no permite cambiar el envío.
    :raises ShippingMethodNotAvailableError: si el método no existe o está inactivo.
    """

    if order_status(order) not in SHIPPING_METHOD_EDITABLE_STATUSES:
        raise OrderNotEditableError(
            f'La orden {order.order_number} no permite cambiar el método '
            f'de envío (estado: {order_status(order)}).'
        )

    try:
        new_method = ShippingMethod.objects.get(pk=shipping_method_id, is_active=True)
    except ShippingMethod.DoesNotExist:
        raise ShippingMethodNotAvailableError(
            f'El método de envío {shipping_method_id} no existe o está inactivo.'
        )

    previous_method = order.shipping_method

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
        value.save(update_fields=['shipping_cost', 'total', 'updated_at'])

        order.shipping_method = new_method
        order.save(update_fields=['shipping_method', 'updated_at'])

        OrderStatusLog.objects.create(
            order=order,
            previous_status=order.status,
            new_status=order.status,
            changed_by=changed_by,
            notes=(
                f'Método de envío actualizado: '
                f'{previous_method.name if previous_method else "(sin método previo)"} '
                f'→ {new_method.name} (${new_shipping_cost})'
            ),
        )

    logger.info(
        'Método de envío actualizado para orden %s → %s ($%s)',
        order.order_number, new_method.name, new_shipping_cost,
    )
    return order


# ---------------------------------------------------------------------------
# Servicios del draft (carrito) — V2 unificación orders→sale (DEC-FW-02).
# La implementación vive en el canónico ``addons.sale.services`` (el carrito
# ES ``sale.order`` state='draft'); este re-export preserva los imports de
# los consumidores (cart/wishlist/users/payments/orders views) hasta que V5
# disuelva la fachada ``orders``.
# ---------------------------------------------------------------------------
from addons.sale.services import (  # noqa: F401  (re-export)
    DraftOrderError,
    add_item_to_draft,
    apply_voucher_to_draft,
    clear_draft_items,
    confirm_draft_order,
    get_draft_totals,
    get_or_create_draft_order,
    merge_draft_orders,
    remove_draft_item,
    remove_voucher_from_draft,
)
