"""
OrderService — addons.orders
Sprint 18 — UC-ORD-04, UC-ORD-05, UC-ORD-06

Orquesta cancelación, edición de dirección y cambio de método de envío.
Centraliza la lógica de negocio fuera de las vistas.
"""
import logging
from uuid import uuid4
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from addons.inventory.services import InventoryService
from .models import Order, OrderAddress, OrderStatusLog
from addons.payments.services import execute_refund
from addons.delivery.models import ShippingMethod


logger = logging.getLogger('apps')

# ─── Estados que permiten cada operación ────────────────────────────────────
# H-ORD-002: mapeo FR→modelo (PENDING_PAYMENT→PENDING, PAYMENT_CONFIRMED→PROCESSING)
# H-ORD-S01: PAID debe incluirse — pago confirmado pero aún no en preparación.
CANCELABLE_STATUSES = ['PENDING', 'PROCESSING', 'PAID']
EDITABLE_STATUSES   = ['PENDING', 'PROCESSING', 'PAID', 'IN_PREPARATION']  # dirección
# D-3 (UC-ORD-06): cambiar el método de envío recalcula el total; en una orden
# ya pagada (PAID/IN_PREPARATION) eso deja el pago capturado sin conciliar
# (cobro/reembolso de la diferencia no implementado). Se restringe a estados
# PRE-pago (pago aún no confirmado — el webhook transiciona PENDING/PROCESSING
# → PAID), de modo que el recálculo siempre precede a la captura del pago.
SHIPPING_METHOD_EDITABLE_STATUSES = ['PENDING', 'PROCESSING']


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
        previous_status           = order.status
        order.status              = 'CANCELLED'
        order.cancellation_reason = reason
        order.cancelled_at        = timezone.now()
        order.save(update_fields=['status', 'cancellation_reason', 'cancelled_at', 'updated_at'])

        # Registrar transición en el log de auditoría — UC-ORD-04
        OrderStatusLog.objects.create(
            order=order,
            previous_status=previous_status,
            new_status='CANCELLED',
            changed_by=cancelled_by,
            notes=reason,
        )

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

    if order.status not in EDITABLE_STATUSES:
        raise ValueError(
            f'La orden {order.order_number} no permite editar la dirección '
            f'(estado: {order.status}). La guía de envío ya fue creada.'
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

    if order.status not in SHIPPING_METHOD_EDITABLE_STATUSES:
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


def get_or_create_draft_order(user=None, cart_token=None):
    """S2 unificación cart→order→sale (analisis-unificar-cart-order-sale).

    Espejo de ``cart.views._get_or_create_cart`` sobre ``Order(DRAFT)``:

    - Autenticado (``user``): un único draft por usuario — MariaDB no
      soporta UNIQUE parcial, así que la unicidad one-draft-per-user se
      garantiza aquí (``get_or_create`` sobre el draft más reciente).
    - Anónimo (``cart_token``): busca/crea el draft por token (columna
      UNIQUE; múltiples NULL permitidos).

    Retorna ``(order, created)``. No toca ``Cart``/``CartItem`` — la
    paridad de vistas y la data migration llegan en S2b/S4.
    """
    if user is not None and getattr(user, 'is_authenticated', False):
        draft = (Order.objects
                 .filter(user=user, status=Order.STATUS_DRAFT)
                 .order_by('-created_at')
                 .first())
        if draft is not None:
            return draft, False
        return Order.objects.create(user=user, status=Order.STATUS_DRAFT), True

    if cart_token is None:
        return Order.objects.create(status=Order.STATUS_DRAFT,
                                    cart_token=uuid4()), True
    order, created = Order.objects.get_or_create(
        cart_token=cart_token, defaults={'status': Order.STATUS_DRAFT})
    return order, created


class DraftOrderError(ValueError):
    """Errores de operación sobre el draft order (S2b). ``codigo_error``
    lleva el código canónico que la vista sella en la respuesta."""

    def __init__(self, message, codigo_error):
        super().__init__(message)
        self.codigo_error = codigo_error


def add_item_to_draft(order, product, variant=None, quantity=1):
    """S2b unificación cart→order→sale: agrega/mezcla un item en el draft.

    Paridad con ``cart.views.CartView.post`` (UC-CART-02): guard de stock
    doble (antes y dentro del atomic, H-CICLO121-01), merge de cantidad si
    el item ya existe, y precio vigente al momento de la operación
    (``variant.effective_price()`` o ``product.price``). A diferencia de
    ``CartItem``, el ``OrderItem`` del draft ya carga el snapshot
    (``product_name``/``sku``/``variant_label``) — se refresca en cada
    operación mientras la orden siga en ``DRAFT``; ``action_confirm`` (S3)
    lo congela.
    """
    if order.status != Order.STATUS_DRAFT:
        raise DraftOrderError('La orden no es un draft.', 'ORDEN_NO_DRAFT')
    if quantity < 1:
        raise DraftOrderError('quantity debe ser >= 1.', 'CANTIDAD_INVALIDA')

    available = variant.stock if variant else product.stock
    if available is not None and available <= 0:
        raise DraftOrderError('Producto sin stock.', 'OUT_OF_STOCK')
    if available is not None and quantity > available:
        raise DraftOrderError('Stock insuficiente.', 'INSUFFICIENT_STOCK')

    unit_price = variant.effective_price() if variant else product.price
    label      = variant.option.label if variant else ''
    sku        = variant.sku if variant else product.sku

    with transaction.atomic():
        item, created = order.items.get_or_create(
            product=product, variant=variant,
            defaults={
                'product_name': product.name,
                'variant_label': label,
                'sku': sku,
                'unit_price': unit_price,
                'quantity': quantity,
                'subtotal': unit_price * quantity,
            },
        )
        if not created:
            new_qty = item.quantity + quantity
            avail = variant.stock if variant else product.stock
            if avail is not None and new_qty > avail:
                raise DraftOrderError('Stock insuficiente.', 'INSUFFICIENT_STOCK')
            item.quantity   = new_qty
            item.unit_price = unit_price
            item.subtotal   = unit_price * new_qty
            item.save(update_fields=['quantity', 'unit_price', 'subtotal',
                                     'updated_at'])
    return item, created


def clear_draft_items(order):
    """S2b: vacía el draft (paridad con ``CartView.delete``, UC-CART-03)."""
    if order.status != Order.STATUS_DRAFT:
        raise DraftOrderError('La orden no es un draft.', 'ORDEN_NO_DRAFT')
    order.items.all().delete()
