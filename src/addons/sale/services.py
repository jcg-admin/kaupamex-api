"""Servicios del draft (carrito) — addon ``sale``.

V2 unificación orders→sale (``analisis-unificar-orders-sale``, DEC-FW-02):
los servicios del draft que S2/S3 construyeron sobre el strangler
``orders.Order`` se conmutan aquí al canónico ``sale.SaleOrder`` +
``SaleOrderLine`` — en Odoo el carrito ES ``sale.order`` con
``state='draft'`` y estos servicios son la adaptación de ``website_sale``
(cart update/merge) + ``sale.order.action_confirm``.

El voucher del draft deja de anclarse por ``voucher_code`` string y pasa a
``sale_loyalty.SaleOrderCoupon`` (OneToOne a la orden) — cierra
H-CART-CL-02.

``confirm_draft_order`` confirma la ``SaleOrder`` nativamente
(``action_confirm``): la venta **es** la orden. El puente transicional que
materializaba el espejo ``orders.Order`` desapareció con el addon (SOL-098,
``api@77bd1f0``); pagos, logística y post-venta consumen la canónica
directamente.
"""
import logging
from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from addons.sale.models import SaleOrder
from addons.delivery.models import DeliveryAddress
from django.db.models import F
from django.utils import timezone

from addons.base_setup.settings_access import get_setting
from addons.stock.services import InventoryService
from addons.loyalty.models import Voucher, VoucherUsage
from addons.stock.models import StockPicking
from addons.mail.models.notification_service import notify_order_status_changed
from .status_projection import STATUS_CANCELLED, order_status
from .models import SaleOrder, SaleOrderLine
from .signals import (draft_discount_requested, order_cancelled,
                      draft_voucher_requested, order_confirmed)


logger = logging.getLogger('apps')


class DraftOrderError(ValueError):
    """Errores de operación sobre el draft. ``codigo_error`` lleva el
    código canónico que la vista sella en la respuesta."""

    def __init__(self, message, codigo_error):
        super().__init__(message)
        self.codigo_error = codigo_error


def get_or_create_draft_order(user=None, cart_token=None):
    """Resuelve el ``SaleOrder(draft)`` que hace de carrito activo.

    - Autenticado (``user``): un único draft por partner. La unicidad la
      garantiza la **base** — ``SaleOrder.Meta.constraints`` declara un
      índice único parcial sobre ``partner`` restringido a
      ``state='draft'`` (H-API-309). Esta función ya no la sostiene: sólo
      resuelve o crea.
    - Anónimo (``cart_token``): busca/crea el draft por token (columna
      UNIQUE; múltiples NULL permitidos — verificado en PostgreSQL).

    Retorna ``(order, created)``.
    """
    if user is not None and getattr(user, 'is_authenticated', False):
        draft = (SaleOrder.objects
                 .filter(partner=user, state=SaleOrder.STATE_DRAFT)
                 .order_by('-created_at')
                 .first())
        if draft is not None:
            return draft, False
        return SaleOrder.objects.create(
            partner=user, state=SaleOrder.STATE_DRAFT), True

    if cart_token is None:
        return SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, cart_token=uuid4()), True
    order, created = SaleOrder.objects.get_or_create(
        cart_token=cart_token, defaults={'state': SaleOrder.STATE_DRAFT})
    return order, created


def _line_snapshot_name(product):
    """Descripción de la línea (Odoo ``sale.order.line.name``).

    ``product`` es la **variante** (``product.product``): su ``display_name``
    ya incluye los valores de atributo, así que no hay que componerlo desde un
    eje ``variant`` aparte (odoo19c: ``product/models/product_product.py``).
    """
    return str(product)


def add_item_to_draft(order, product, quantity=1):
    """Agrega/mezcla una línea en el draft (UC-CART-02).

    ``product`` es la **variante** (``product.product``), fiel a
    ``odoo19c: addons/sale/models/sale_order_line.py:83-88``. El parámetro
    ``variant`` desapareció: era el mismo dato en un segundo eje, herencia del
    modelo plano previo a la separación plantilla/variante (H-API-213).

    Guard de stock doble (antes y dentro del atomic, H-CICLO121-01),
    merge de cantidad si la línea ya existe, y precio vigente al momento de la
    operación. La existencia se **deriva** de ``stock.quant`` vía
    ``InventoryService``, no de una columna del producto (odoo19c:
    ``stock/models/stock_quant.py:119-122``).
    """
    if order.state != SaleOrder.STATE_DRAFT:
        raise DraftOrderError('La orden no es un draft.', 'ORDER_NOT_DRAFT')
    if quantity < 1:
        raise DraftOrderError('quantity debe ser >= 1.', 'INVALID_QUANTITY')

    available = InventoryService.available_quantity(product)
    if available <= 0:
        raise DraftOrderError('Producto sin stock.', 'OUT_OF_STOCK')
    if quantity > available:
        raise DraftOrderError('Stock insuficiente.', 'INSUFFICIENT_STOCK')

    unit_price = product.lst_price

    with transaction.atomic():
        line, created = order.order_line.get_or_create(
            product=product,
            defaults={
                'name': _line_snapshot_name(product),
                'price_unit': unit_price,
                'product_uom_qty': quantity,
            },
        )
        if not created:
            new_qty = line.product_uom_qty + quantity
            avail = InventoryService.available_quantity(product)
            if new_qty > avail:
                raise DraftOrderError('Stock insuficiente.', 'INSUFFICIENT_STOCK')
            line.product_uom_qty = new_qty
            line.price_unit = unit_price
            line.save(update_fields=['product_uom_qty', 'price_unit',
                                     'updated_at'])
    return line, created


def clear_draft_items(order):
    """Vacía el draft (UC-CART-03).

    ``QuerySet.delete()`` en bloque no dispara el recálculo de
    ``SaleOrderLine.delete()`` (H-API-30) — se dispara explícito para que el
    total de la orden quede en ``0.00`` y no stale con el value previo.
    """
    if order.state != SaleOrder.STATE_DRAFT:
        raise DraftOrderError('La orden no es un draft.', 'ORDER_NOT_DRAFT')
    order.order_line.all().delete()
    order._compute_amounts()


def _draft_extra_discount(order, subtotal):
    """Descuento aportado por los satélites sobre el draft (T-034).

    El núcleo NO conoce el cupón: emite ``draft_discount_requested`` y suma
    lo que respondan los receptores. Hoy responde ``sale_loyalty`` con el
    descuento vivo de su ``SaleOrderCoupon``; si el addon no está instalado
    no hay receptores y el descuento es ``0.00``.

    Es la traducción a Django del ``_inherit`` de la referencia, donde
    ``sale_loyalty`` extiende ``sale.order`` sin que ``sale`` lo declare.
    """
    respuestas = draft_discount_requested.send(
        sender=SaleOrder, order=order, subtotal=subtotal)
    return sum(
        (value for _receptor, value in respuestas if value),
        Decimal('0.00'),
    )


def get_draft_totals(order):
    """Totales del draft con el MISMO contrato de 13 claves servido desde
    S2c (paridad con el histórico ``Cart.get_totals`` — el storefront
    consume este dict tal cual). El descuento se recalcula VIVO desde el
    ``SaleOrderCoupon`` mientras la orden siga en draft (los items cambian
    y el descuento los sigue); ``confirm_draft_order`` lo congela en el
    espejo legacy.
    """
    iva_rate  = get_setting('iva_rate')
    threshold = get_setting('free_shipping_threshold')
    threshold = threshold if threshold > 0 else None

    lines    = list(order.order_line.all())
    subtotal = sum((l.price_unit * l.product_uom_qty for l in lines),
                   Decimal('0.00'))
    discount = Decimal('0.00')
    if order.state == SaleOrder.STATE_DRAFT:
        discount = _draft_extra_discount(order, subtotal)
    subtotal_net = subtotal - discount
    tax = (subtotal_net * iva_rate / (1 + iva_rate)).quantize(Decimal('0.01'))
    free_remaining = (
        max(Decimal('0.00'), threshold - subtotal_net) if threshold else None
    )
    amount_tax = sum((l.price_tax() for l in lines), Decimal('0.00'))
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
        'item_count': len(lines),
    }


def update_draft_item_quantity(order, item_pk, quantity):
    """Fija la cantidad de una línea del draft (UC-CART-02)."""
    if order.state != SaleOrder.STATE_DRAFT:
        raise DraftOrderError('La orden no es un draft.', 'ORDER_NOT_DRAFT')
    if quantity < 1:
        raise DraftOrderError('quantity debe ser >= 1.', 'INVALID_QUANTITY')
    line = order.order_line.filter(pk=item_pk).first()
    if line is None:
        raise DraftOrderError('Item no encontrado.', 'ITEM_NOT_FOUND')
    stock = InventoryService.available_quantity(line.product)
    if quantity > stock:
        raise DraftOrderError('Stock insuficiente.', 'INSUFFICIENT_STOCK')
    line.product_uom_qty = quantity
    line.save(update_fields=['product_uom_qty', 'updated_at'])
    return line


def remove_draft_item(order, item_pk):
    """Elimina una línea del draft (UC-CART-03)."""
    if order.state != SaleOrder.STATE_DRAFT:
        raise DraftOrderError('La orden no es un draft.', 'ORDER_NOT_DRAFT')
    line = order.order_line.filter(pk=item_pk).first()
    if line is None:
        raise DraftOrderError('Item no encontrado.', 'ITEM_NOT_FOUND')
    line.delete()


def merge_draft_orders(user, cart_token):
    """Fusiona el draft anónimo (por token) en el draft del usuario
    autenticado (UC-CART-06, H-CICLO20-02): líneas sin stock se omiten y
    se reportan en ``skipped``; cantidades se recortan al stock
    disponible al mezclar.

    Retorna ``(order, skipped)``. Si no existe draft anónimo con ese
    token (o ya pertenece a un partner), retorna el draft del usuario
    intacto.
    """
    auth_order, _ = get_or_create_draft_order(user=user)
    anon_order = (SaleOrder.objects
                  .filter(cart_token=cart_token,
                          state=SaleOrder.STATE_DRAFT,
                          partner__isnull=True)
                  .exclude(pk=auth_order.pk)
                  .first())
    if anon_order is None:
        return auth_order, []

    skipped = []
    with transaction.atomic():
        for anon_line in anon_order.order_line.select_related('product').all():
            available = InventoryService.available_quantity(anon_line.product)
            if available <= 0:
                skipped.append({'product_id': anon_line.product_id,
                                'product_name': anon_line.name,
                                'reason': 'OUT_OF_STOCK'})
                continue

            existing = auth_order.order_line.filter(
                product=anon_line.product).first()
            if existing:
                new_qty = existing.product_uom_qty + anon_line.product_uom_qty
                if new_qty > available:
                    new_qty = available
                existing.product_uom_qty = new_qty
                existing.price_unit = anon_line.price_unit
                existing.save(update_fields=['product_uom_qty', 'price_unit',
                                             'updated_at'])
            else:
                merge_qty = anon_line.product_uom_qty
                if merge_qty > available:
                    merge_qty = available
                auth_order.order_line.create(
                    product=anon_line.product,
                    name=anon_line.name,
                    price_unit=anon_line.price_unit,
                    product_uom_qty=merge_qty,
                )
        anon_order.delete()
    return auth_order, skipped


def confirm_draft_order(order, *, address_data, guest_email=None, notes='',
                        shipping_cost=Decimal('0.00')):
    """Confirma el carrito: la transición nativa ``sale.order.action_confirm``
    (draft → sale: acuña ``name`` S-XXXX, fija ``date_order``).

    Pasos (misma semántica del checkout UC-ORD-01):

    1. Guards: orden draft + con líneas.
    2. Disponibilidad de stock (``InventoryService.check_availability``).
    3. Atómico: decrement con SELECT FOR UPDATE; refresco del snapshot de
       línea al precio VIGENTE (H-CICLO78-04); ``action_confirm``;
       consumo del voucher del cupón (DEC-VCU-01 / DEC-BC-10) y
       liberación de ``cart_token`` (el token de la cookie debe poder
       acuñar un draft nuevo).
    4. Materializa la dirección de entrega (``delivery.DeliveryAddress``):
       por la referencia no es del eje comercial, así que vive en
       ``delivery``, no en la orden. Retorna la ``SaleOrder`` confirmada —
       ya no hay espejo que devolver.

    Levanta ``DraftOrderError`` en los guards; propaga
    ``InsufficientStockError``/``IntegrityError`` para que la vista selle
    los mismos ``codigo_error`` históricos.
    """
    if order.state != SaleOrder.STATE_DRAFT:
        raise DraftOrderError('La orden no es un draft.', 'ORDER_NOT_DRAFT')

    # E1-bis — SÓLO líneas de producto. Las líneas marcadoras
    # (``is_delivery``/``is_reward``, materializadas por ``delivery`` y
    # ``sale_loyalty`` antes de confirmar) NO son vendibles: no reservan stock,
    # no se refrescan a precio vigente —su ``current_price()`` devolvería el
    # precio 0 del producto de servicio, borrando el importe— y no cruzan al
    # espejo legacy, cuyos ``SaleOrderLine`` son de producto por contrato.
    # Un carrito con sólo líneas marcadoras está vacío.
    lines = list(order.order_line.filter(is_delivery=False, is_reward=False)
                 .select_related('product'))
    if not lines:
        raise DraftOrderError('El carrito está vacío.', 'EMPTY_CART')

    check_items = [{'product': l.product,
                    'quantity': l.product_uom_qty} for l in lines]
    insufficient = InventoryService.check_availability(check_items)
    if insufficient:
        err = DraftOrderError('Stock insuficiente para algunos items.',
                              'INSUFFICIENT_STOCK')
        err.items = insufficient
        raise err

    iva_rate = get_setting('iva_rate')
    respuestas = draft_voucher_requested.send(sender=SaleOrder, order=order)
    voucher = next((v for _r, v in respuestas if v is not None), None)

    with transaction.atomic():
        InventoryService.decrement(check_items)

        subtotal = Decimal('0.00')
        for line in lines:
            live_price = line.current_price()
            subtotal  += live_price * line.product_uom_qty
            line.price_unit = live_price
            line.name = _line_snapshot_name(line.product)
            line.save(update_fields=['price_unit', 'name', 'updated_at'])

        voucher_discount = (voucher.calculate_discount(subtotal)
                            if voucher else Decimal('0.00'))
        net   = subtotal - voucher_discount
        tax   = (net * iva_rate / (1 + iva_rate)).quantize(Decimal('0.01'))
        total = net + shipping_cost

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
            if order.partner_id:
                VoucherUsage.objects.create(user=order.partner, voucher=voucher)

        # Transición nativa + campos del comprador + liberación del token.
        order.notes = notes or order.notes
        if guest_email and not order.partner_id:
            order.guest_email = guest_email
        order.cart_token = None
        order.save(update_fields=['notes', 'guest_email', 'cart_token',
                                  'updated_at'])
        order.action_confirm()

        # Sub-estado de fulfillment (V5b — analisis-unificar-orders-sale,
        # H-SALE-09). En Odoo action_confirm crea el albarán vía sale_stock;
        # aquí poblamos el eje canónico para que IN_PREPARATION sea derivable
        # (albarán ``assigned`` + ``delivery_status='started'`` sin guía) sin
        # depender del enum monolítico ``SaleOrder.status``. Additivo: modelos
        # dormidos, ningún lector vivo depende de ellos todavía.
        picking = StockPicking.objects.create(
            sale_order=order, state=StockPicking.STATE_CONFIRMED)
        picking.action_assign()
        # Los satélites reaccionan a la confirmación (T-034): ``sale_stock``
        # abre el seguimiento de entrega. El núcleo no los nombra.
        order_confirmed.send(sender=SaleOrder, order=order, subtotal=subtotal)

        # E5 — el puente al espejo desapareció con el addon ``orders``.
        # La venta canónica YA tiene su identidad (``name`` acuñado por
        # ``action_confirm``), sus líneas (``SaleOrderLine``) y sus importes
        # (``amount_untaxed``/``amount_tax``/``amount_total``, E4). Lo único
        # que faltaba materializar es la dirección de entrega, que por la
        # referencia no es del eje comercial: vive en ``delivery``.
        DeliveryAddress.objects.create(sale_order=order, **address_data)
    return order


def track_sale_state(order, previous, new, author, note=''):
    """Registra una transición de estado de la venta en su chatter.

    Reemplaza a ``orders.OrderStatusLog``. El destino lo declara
    ``analisis-estructura-destino-comercial.rst``: en la referencia la bitácora
    es ``mail.thread`` con ``tracking=True`` sobre el campo, no una tabla
    lateral. ``SaleOrder`` ya hereda ``MailThread``, así que la paridad es
    directa: ``changed_by`` → autor del ``mail.message``; los estados →
    ``old``/``new`` del ``mail.tracking.value``.

    La nota va como mensaje aparte porque ``message_track`` publica el
    tracking con cuerpo vacío (fiel a Odoo, donde el comentario es otro
    mensaje del hilo).

    Vive aquí y no en ``delivery`` —donde nació— porque el sujeto es el estado
    de la **venta**: ``delivery`` depende de ``sale``, nunca al revés.
    """
    order.message_track(
        [{'field': 'state', 'field_desc': 'Estado', 'field_type': 'char',
          'old': previous, 'new': new}],
        author=author,
    )
    if note:
        order.message_post(body=note, author=author)


# Cancelable por el **comprador**. Una vez despachada la orden, la vuelta
# atrás es una devolución (``returns``), no una cancelación.
CANCELABLE_STATUSES = ['PENDING', 'PAID']


def cancel_order(order, reason='', cancelled_by=None, cancelable_statuses=None):
    """Cancela una venta de forma atómica (UC-ORD-04).

    Cuatro pasos en una sola transacción: validar que el estado proyectado sea
    cancelable, cancelar el eje comercial, restaurar el stock de las líneas de
    producto, y reembolsar si hay un pago aprobado.

    El estado **no se escribe**: se cancela ``action_cancel()`` y la proyección
    deriva CANCELLED de ahí. Los campos de metadata de la cancelación
    (``cancellation_reason``/``cancelled_at``) sí son columnas de la venta.

    :raises ValueError: si la orden no es cancelable.
    :raises RuntimeError: si el gateway de reembolso falla (revierte todo).
    """
    allowed = (cancelable_statuses if cancelable_statuses is not None
               else CANCELABLE_STATUSES)
    if order_status(order) not in allowed:
        raise ValueError(
            f'La orden {order.name} no se puede cancelar '
            f'(estado: {order_status(order)}). Solo se permiten cancelaciones '
            f'en estados: {allowed}.'
        )

    with transaction.atomic():
        # Re-verificar bajo lock: dos cancelaciones concurrentes restaurarían
        # el stock dos veces. Se re-deriva el estado sobre la fila bloqueada.
        order = SaleOrder.objects.select_for_update().get(pk=order.pk)
        if order_status(order) not in allowed:
            raise ValueError(
                f'La orden {order.name} ya no es cancelable '
                f'(cancelada por una petición concurrente).'
            )

        previous_status = order_status(order)
        order.cancellation_reason = reason
        order.cancelled_at        = timezone.now()
        order.save(update_fields=['cancellation_reason', 'cancelled_at',
                                  'updated_at'])

        if order.state != SaleOrder.STATE_CANCEL and not order.locked:
            order.action_cancel()

        track_sale_state(order, previous_status, STATUS_CANCELLED,
                         cancelled_by, note=reason)
        notify_order_status_changed(order, STATUS_CANCELLED)

        # Restaurar stock — sólo las líneas de producto: las marcadoras de
        # envío y descuento no reservaron nada que devolver.
        stock_items = [
            {'product': line.product, 'quantity': line.product_uom_qty}
            for line in (order.order_line
                         .filter(is_delivery=False, is_reward=False)
                         .select_related('product'))
            if line.product_id
        ]
        if stock_items:
            InventoryService.restore(
                items=stock_items, reference=order.name,
                created_by=cancelled_by,
            )
            logger.info('Stock restaurado para la orden cancelada %s — %d líneas',
                        order.name, len(stock_items))

        # El reembolso lo hace ``payments`` al escuchar la señal: el núcleo
        # no puede importarlo (``Payment`` tiene FK a ``SaleOrder``). Si el
        # gateway falla, el receptor levanta y revierte la transacción entera
        # — cancelar sin devolver el dinero dejaría al comprador pagado y sin
        # orden.
        order_cancelled.send(sender=SaleOrder, order=order, reason=reason,
                             cancelled_by=cancelled_by)

    return order
