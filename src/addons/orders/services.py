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
from django.db.models import F
from addons.inventory.services import InventoryService
from .models import Order, OrderAddress, OrderStatusLog, OrderValue
from addons.base.models import SiteSettings
from addons.loyalty.models import Voucher, VoucherUsage
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


def get_draft_totals(order):
    """S2c unificación cart→order→sale: totales del draft con el MISMO
    contrato de ``cart.Cart.get_totals`` (paridad de claves — el storefront
    consume este dict tal cual). El descuento sale de
    ``order.voucher_discount`` (en el draft aún 0; el voucher se re-ancla a
    ``sale_loyalty`` en una rebanada posterior, H-CART-CL-02). Los importes
    Odoo-canónicos (``amount_*``) se derivan del subtotal por línea +
    ``iva_rate`` — mismo desglose IVA-incluido que ``CartItem.price_*``.
    """
    iva_rate  = SiteSettings.get_current().iva_rate
    threshold = SiteSettings.get_current().free_shipping_threshold
    threshold = threshold if threshold > 0 else None

    items    = list(order.items.all())
    subtotal = sum((i.unit_price * i.quantity for i in items), Decimal('0.00'))
    # En DRAFT el descuento se recalcula VIVO desde el voucher aplicado
    # (paridad con Cart.get_discount: los items cambian y el descuento
    # los sigue). confirm_draft_order congela voucher_discount al confirmar.
    discount = order.voucher_discount or Decimal('0.00')
    if order.status == Order.STATUS_DRAFT and order.voucher_code:
        voucher = Voucher.objects.filter(code=order.voucher_code).first()
        discount = (voucher.calculate_discount(subtotal)
                    if voucher else Decimal('0.00'))
    subtotal_net = subtotal - discount
    tax = (subtotal_net * iva_rate / (1 + iva_rate)).quantize(Decimal('0.01'))
    free_remaining = (
        max(Decimal('0.00'), threshold - subtotal_net) if threshold else None
    )
    amount_tax = sum(
        ((i.unit_price * i.quantity * iva_rate / (1 + iva_rate)).quantize(Decimal('0.01'))
         for i in items),
        Decimal('0.00'),
    )
    return {
        'subtotal':                str(subtotal),
        'discount':                str(discount),
        'subtotal_net':            str(subtotal_net),
        'tax_included':            str(tax),
        'shipping_cost':           None,
        'total':                   str(subtotal_net),
        'free_shipping_threshold': str(threshold) if threshold else None,
        'free_shipping_remaining': str(free_remaining) if free_remaining else None,
        'free_shipping_applied':   bool(threshold and subtotal_net >= threshold),
        'amount_untaxed': str(subtotal - amount_tax),
        'amount_tax':     str(amount_tax),
        'amount_total':   str(subtotal),
        'item_count': len(items),
    }


def update_draft_item_quantity(order, item_pk, quantity):
    """S2c: fija la cantidad de un item del draft (paridad con
    ``CartItemDetailView.patch``, UC-CART-02): guard de stock sobre el
    valor absoluto y refresco de ``subtotal``."""
    if order.status != Order.STATUS_DRAFT:
        raise DraftOrderError('La orden no es un draft.', 'ORDEN_NO_DRAFT')
    if quantity < 1:
        raise DraftOrderError('quantity debe ser >= 1.', 'CANTIDAD_INVALIDA')
    item = order.items.filter(pk=item_pk).first()
    if item is None:
        raise DraftOrderError('Item no encontrado.', 'ITEM_NOT_FOUND')
    stock = item.variant.stock if item.variant else (
        item.product.stock if item.product else None)
    if stock is not None and quantity > stock:
        raise DraftOrderError('Stock insuficiente.', 'INSUFFICIENT_STOCK')
    item.quantity = quantity
    item.subtotal = item.unit_price * quantity
    item.save(update_fields=['quantity', 'subtotal', 'updated_at'])
    return item


def remove_draft_item(order, item_pk):
    """S2c: elimina un item del draft (paridad con
    ``CartItemDetailView.delete``, UC-CART-03)."""
    if order.status != Order.STATUS_DRAFT:
        raise DraftOrderError('La orden no es un draft.', 'ORDEN_NO_DRAFT')
    item = order.items.filter(pk=item_pk).first()
    if item is None:
        raise DraftOrderError('Item no encontrado.', 'ITEM_NOT_FOUND')
    item.delete()


def merge_draft_orders(user, cart_token):
    """S2c-2b: fusiona el draft anónimo (por token) en el draft del usuario
    autenticado — paridad con ``CartMergeView.post`` (UC-CART-06,
    H-CICLO20-02): items sin stock se omiten y se reportan en ``skipped``;
    cantidades se recortan al stock disponible al mezclar.

    Retorna ``(order, skipped)``. Si no existe draft anónimo con ese token
    (o ya pertenece a un usuario), retorna el draft del usuario intacto.
    """
    auth_order, _ = get_or_create_draft_order(user=user)
    anon_order = (Order.objects
                  .filter(cart_token=cart_token, status=Order.STATUS_DRAFT,
                          user__isnull=True)
                  .exclude(pk=auth_order.pk)
                  .first())
    if anon_order is None:
        return auth_order, []

    skipped = []
    with transaction.atomic():
        for anon_item in anon_order.items.select_related('product', 'variant').all():
            if anon_item.product is None:
                skipped.append({'product_id': None,
                                'product_name': anon_item.product_name,
                                'reason': 'PRODUCT_UNAVAILABLE'})
                continue
            available = (anon_item.variant.stock if anon_item.variant
                         else anon_item.product.stock)
            if available is not None and available <= 0:
                skipped.append({'product_id': anon_item.product.pk,
                                'product_name': anon_item.product_name,
                                'reason': 'OUT_OF_STOCK'})
                continue

            existing = auth_order.items.filter(
                product=anon_item.product, variant=anon_item.variant).first()
            if existing:
                new_qty = existing.quantity + anon_item.quantity
                if available is not None and new_qty > available:
                    new_qty = available
                existing.quantity   = new_qty
                existing.unit_price = anon_item.unit_price
                existing.subtotal   = anon_item.unit_price * new_qty
                existing.save(update_fields=['quantity', 'unit_price',
                                             'subtotal', 'updated_at'])
            else:
                merge_qty = anon_item.quantity
                if available is not None and merge_qty > available:
                    merge_qty = available
                auth_order.items.create(
                    product=anon_item.product,
                    variant=anon_item.variant,
                    product_name=anon_item.product_name,
                    variant_label=anon_item.variant_label,
                    sku=anon_item.sku,
                    unit_price=anon_item.unit_price,
                    quantity=merge_qty,
                    subtotal=anon_item.unit_price * merge_qty,
                )
        anon_order.delete()
    return auth_order, skipped


def apply_voucher_to_draft(order, code, user=None):
    """S3: aplica un voucher al draft (paridad con ``CartVoucherView.post``,
    UC-CART-04 + H-CICLO112-01). El draft ancla el voucher por
    ``voucher_code`` (snapshot-friendly: es el mismo campo que el checkout
    congela); el descuento NO se congela aquí — ``get_draft_totals`` lo
    recalcula vivo mientras la orden siga en DRAFT. Retorna
    ``(voucher, discount, cart_total)``.
    """
    if order.status != Order.STATUS_DRAFT:
        raise DraftOrderError('La orden no es un draft.', 'ORDEN_NO_DRAFT')
    voucher = Voucher.objects.filter(code=code).first()
    if voucher is None:
        raise DraftOrderError('El voucher no existe.', 'VOUCHER_NOT_FOUND')

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        cart_total = sum(
            (i.unit_price * i.quantity for i in order.items.all()),
            Decimal('0.00'))

        error_code = voucher.validate_for_cart(cart_total, user)
        if error_code:
            raise DraftOrderError(f'Voucher no aplicable: {error_code}',
                                  error_code)
        if user is not None and getattr(user, 'is_authenticated', False):
            if VoucherUsage.objects.filter(user=user, voucher=voucher).exists():
                raise DraftOrderError('Ya has utilizado este voucher.',
                                      'VOUCHER_ALREADY_USED')
        if order.voucher_code:
            raise DraftOrderError(
                'El carrito ya tiene un voucher aplicado. Elimínelo primero.',
                'VOUCHER_ALREADY_APPLIED')

        order.voucher_code = voucher.code
        order.save(update_fields=['voucher_code', 'updated_at'])

    return voucher, voucher.calculate_discount(cart_total), cart_total


def remove_voucher_from_draft(order):
    """S3: quita el voucher del draft (paridad con ``CartVoucherView.delete``)."""
    if not order.voucher_code:
        raise DraftOrderError('El carrito no tiene voucher aplicado.',
                              'NO_ACTIVE_VOUCHER')
    order.voucher_code = ''
    order.voucher_discount = Decimal('0.00')
    order.save(update_fields=['voucher_code', 'voucher_discount', 'updated_at'])


def confirm_draft_order(order, *, address_data, guest_email=None, notes='',
                        shipping_cost=Decimal('0.00')):
    """S3 unificación cart→order→sale: el checkout deja de ser copy-and-delete
    y pasa a ser la **transición** ``DRAFT→PENDING`` — la adaptación de
    ``sale.order.action_confirm`` de Odoo (el carrito ES la orden; confirmar
    no crea nada, congela y transiciona).

    Pasos (misma semántica que el CheckoutView histórico, UC-ORD-01):

    1. Guards: orden DRAFT + con items.
    2. Disponibilidad de stock (``InventoryService.check_availability``).
    3. Atómico: decrement con SELECT FOR UPDATE; refresco del snapshot al
       precio VIGENTE (H-CICLO78-04: ``current_price()``, no el precio del
       add-to-cart); congela ``voucher_discount``; crea ``OrderValue`` y
       ``OrderAddress``; incrementa ``Voucher.current_uses`` + registra
       ``VoucherUsage`` (DEC-VCU-01 / DEC-BC-10); transiciona a PENDING y
       **libera** ``cart_token`` (el token de la cookie debe poder acuñar
       un draft nuevo — si la orden confirmada lo retuviera,
       ``get_or_create_draft_order`` devolvería una orden no-draft).

    Levanta ``DraftOrderError`` en los guards; propaga
    ``InsufficientStockError``/``IntegrityError`` para que la vista selle
    los mismos ``codigo_error`` históricos.
    """
    if order.status != Order.STATUS_DRAFT:
        raise DraftOrderError('La orden no es un draft.', 'ORDEN_NO_DRAFT')

    items = list(order.items.select_related(
        'product', 'variant__product', 'variant__option').all())
    if not items:
        raise DraftOrderError('El carrito está vacío.', 'EMPTY_CART')
    if any(i.product is None for i in items):
        raise DraftOrderError('Hay items de productos eliminados.',
                              'PRODUCT_UNAVAILABLE')

    check_items = [{'product': i.product, 'variant': i.variant,
                    'quantity': i.quantity} for i in items]
    insufficient = InventoryService.check_availability(check_items)
    if insufficient:
        err = DraftOrderError('Stock insuficiente para algunos items.',
                              'INSUFFICIENT_STOCK')
        err.items = insufficient
        raise err

    iva_rate = SiteSettings.get_current().iva_rate
    voucher = (Voucher.objects.filter(code=order.voucher_code).first()
               if order.voucher_code else None)

    with transaction.atomic():
        InventoryService.decrement(check_items)

        subtotal = Decimal('0.00')
        for item in items:
            live_price = item.current_price()
            item_sub   = live_price * item.quantity
            subtotal  += item_sub
            item.unit_price = live_price
            item.subtotal   = item_sub
            item.save(update_fields=['unit_price', 'subtotal', 'updated_at'])

        voucher_discount = (voucher.calculate_discount(subtotal)
                            if voucher else Decimal('0.00'))

        net   = subtotal - voucher_discount
        tax   = (net * iva_rate / (1 + iva_rate)).quantize(Decimal('0.01'))
        total = net + shipping_cost
        OrderValue.objects.create(
            order=order, subtotal=subtotal, tax=tax,
            shipping_cost=shipping_cost, discount=voucher_discount,
            total=total,
        )
        OrderAddress.objects.create(order=order, **address_data)

        if voucher is not None:
            voucher_locked = (Voucher.objects.select_for_update()
                              .get(pk=voucher.pk))
            if (voucher_locked.max_uses is not None
                    and voucher_locked.current_uses >= voucher_locked.max_uses):
                raise DraftOrderError(
                    f'Voucher {voucher_locked.code} agotado: '
                    f'{voucher_locked.current_uses}/{voucher_locked.max_uses}.',
                    'VOUCHER_EXHAUSTED')
            Voucher.objects.filter(pk=voucher.pk).update(
                current_uses=F('current_uses') + 1,
                updated_at=timezone.now(),
            )
            if order.user_id:
                VoucherUsage.objects.create(user=order.user, voucher=voucher)

        order.status = Order.STATUS_PENDING
        order.cart_token = None
        order.voucher_discount = voucher_discount
        order.notes = notes or order.notes
        if guest_email and not order.user_id:
            order.guest_email = guest_email
        order.save(update_fields=['status', 'cart_token', 'voucher_discount',
                                  'notes', 'guest_email', 'updated_at'])
    return order
