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

Puente transicional: ``confirm_draft_order`` confirma la ``SaleOrder``
nativamente (``action_confirm``) y ADEMÁS materializa el espejo legacy
``orders.Order(PENDING)`` + ``SaleOrderLine``/``SaleOrderValue_REMOVED``/``SaleOrderAddress``
que los clusters de pagos/logística/post-venta siguen consumiendo hasta
V3–V5 (el plan retira el espejo en V5). ``orders/services.py`` re-exporta
estas funciones para no romper los imports de los consumidores.
"""
import logging
from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from addons.sale.models import SaleOrder
from addons.delivery.models import DeliveryAddress
from django.db.models import F
from django.utils import timezone

from addons.base.models import SiteSettings
from addons.inventory.services import InventoryService
from addons.loyalty.models import Voucher, VoucherUsage
from addons.stock.models import StockPicking
from .models import SaleOrder, SaleOrderLine
from .signals import (draft_discount_requested,
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

    - Autenticado (``user``): un único draft por partner — MariaDB no
      soporta UNIQUE parcial, la unicidad one-draft-per-partner se
      garantiza aquí (draft más reciente).
    - Anónimo (``cart_token``): busca/crea el draft por token (columna
      UNIQUE; múltiples NULL permitidos).

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


def _line_snapshot_name(product, variant=None):
    """Descripción de la línea (Odoo ``sale.order.line.name``)."""
    if variant is not None:
        return f'{product.name} ({variant.option.label})'
    return product.name


def add_item_to_draft(order, product, variant=None, quantity=1):
    """Agrega/mezcla una línea en el draft (UC-CART-02).

    Guard de stock doble (antes y dentro del atomic, H-CICLO121-01),
    merge de cantidad si la línea ya existe, y precio vigente al momento
    de la operación (``variant.effective_price()`` o ``product.price``).
    El snapshot (``name``/``price_unit``) se refresca mientras la orden
    siga en draft; ``action_confirm`` lo congela.
    """
    if order.state != SaleOrder.STATE_DRAFT:
        raise DraftOrderError('La orden no es un draft.', 'ORDEN_NO_DRAFT')
    if quantity < 1:
        raise DraftOrderError('quantity debe ser >= 1.', 'CANTIDAD_INVALIDA')

    available = variant.stock if variant else product.stock
    if available is not None and available <= 0:
        raise DraftOrderError('Producto sin stock.', 'OUT_OF_STOCK')
    if available is not None and quantity > available:
        raise DraftOrderError('Stock insuficiente.', 'INSUFFICIENT_STOCK')

    unit_price = variant.effective_price() if variant else product.price

    with transaction.atomic():
        line, created = order.order_line.get_or_create(
            product=product, variant=variant,
            defaults={
                'name': _line_snapshot_name(product, variant),
                'price_unit': unit_price,
                'product_uom_qty': quantity,
            },
        )
        if not created:
            new_qty = line.product_uom_qty + quantity
            avail = variant.stock if variant else product.stock
            if avail is not None and new_qty > avail:
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
        raise DraftOrderError('La orden no es un draft.', 'ORDEN_NO_DRAFT')
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
    iva_rate  = SiteSettings.get_current().iva_rate
    threshold = SiteSettings.get_current().free_shipping_threshold
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
        raise DraftOrderError('La orden no es un draft.', 'ORDEN_NO_DRAFT')
    if quantity < 1:
        raise DraftOrderError('quantity debe ser >= 1.', 'CANTIDAD_INVALIDA')
    line = order.order_line.filter(pk=item_pk).first()
    if line is None:
        raise DraftOrderError('Item no encontrado.', 'ITEM_NOT_FOUND')
    stock = line.variant.stock if line.variant else line.product.stock
    if stock is not None and quantity > stock:
        raise DraftOrderError('Stock insuficiente.', 'INSUFFICIENT_STOCK')
    line.product_uom_qty = quantity
    line.save(update_fields=['product_uom_qty', 'updated_at'])
    return line


def remove_draft_item(order, item_pk):
    """Elimina una línea del draft (UC-CART-03)."""
    if order.state != SaleOrder.STATE_DRAFT:
        raise DraftOrderError('La orden no es un draft.', 'ORDEN_NO_DRAFT')
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
        for anon_line in anon_order.order_line.select_related(
                'product', 'variant').all():
            available = (anon_line.variant.stock if anon_line.variant
                         else anon_line.product.stock)
            if available is not None and available <= 0:
                skipped.append({'product_id': anon_line.product_id,
                                'product_name': anon_line.name,
                                'reason': 'OUT_OF_STOCK'})
                continue

            existing = auth_order.order_line.filter(
                product=anon_line.product, variant=anon_line.variant).first()
            if existing:
                new_qty = existing.product_uom_qty + anon_line.product_uom_qty
                if available is not None and new_qty > available:
                    new_qty = available
                existing.product_uom_qty = new_qty
                existing.price_unit = anon_line.price_unit
                existing.save(update_fields=['product_uom_qty', 'price_unit',
                                             'updated_at'])
            else:
                merge_qty = anon_line.product_uom_qty
                if available is not None and merge_qty > available:
                    merge_qty = available
                auth_order.order_line.create(
                    product=anon_line.product,
                    variant=anon_line.variant,
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
    4. Puente V2→V5: materializa el espejo legacy ``orders.Order(PENDING)``
       + ``SaleOrderLine``/``SaleOrderValue_REMOVED``/``SaleOrderAddress`` que pagos/
       logística/post-venta consumen hasta re-anclarse (V3/V4); la
       ``SaleOrderAddress`` ancla a AMBOS (FK dual de V1). Retorna el espejo
       legacy para que la vista selle la misma respuesta 201.

    Levanta ``DraftOrderError`` en los guards; propaga
    ``InsufficientStockError``/``IntegrityError`` para que la vista selle
    los mismos ``codigo_error`` históricos.
    """
    if order.state != SaleOrder.STATE_DRAFT:
        raise DraftOrderError('La orden no es un draft.', 'ORDEN_NO_DRAFT')

    # E1-bis — SÓLO líneas de producto. Las líneas marcadoras
    # (``is_delivery``/``is_reward``, materializadas por ``delivery`` y
    # ``sale_loyalty`` antes de confirmar) NO son vendibles: no reservan stock,
    # no se refrescan a precio vigente —su ``current_price()`` devolvería el
    # precio 0 del producto de servicio, borrando el importe— y no cruzan al
    # espejo legacy, cuyos ``SaleOrderLine`` son de producto por contrato.
    # Un carrito con sólo líneas marcadoras está vacío.
    lines = list(order.order_line.filter(is_delivery=False, is_reward=False)
                 .select_related('product', 'variant__product',
                                 'variant__option'))
    if not lines:
        raise DraftOrderError('El carrito está vacío.', 'EMPTY_CART')

    check_items = [{'product': l.product, 'variant': l.variant,
                    'quantity': l.product_uom_qty} for l in lines]
    insufficient = InventoryService.check_availability(check_items)
    if insufficient:
        err = DraftOrderError('Stock insuficiente para algunos items.',
                              'INSUFFICIENT_STOCK')
        err.items = insufficient
        raise err

    iva_rate = SiteSettings.get_current().iva_rate
    respuestas = draft_voucher_requested.send(sender=SaleOrder, order=order)
    voucher = next((v for _r, v in respuestas if v is not None), None)

    with transaction.atomic():
        InventoryService.decrement(check_items)

        subtotal = Decimal('0.00')
        for line in lines:
            live_price = line.current_price()
            subtotal  += live_price * line.product_uom_qty
            line.price_unit = live_price
            line.name = _line_snapshot_name(line.product, line.variant)
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
