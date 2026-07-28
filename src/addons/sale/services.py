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
``orders.Order(PENDING)`` + ``OrderItem``/``OrderValue``/``OrderAddress``
que los clusters de pagos/logística/post-venta siguen consumiendo hasta
V3–V5 (el plan retira el espejo en V5). ``orders/services.py`` re-exporta
estas funciones para no romper los imports de los consumidores.
"""
import logging
from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from addons.base.models import SiteSettings
from addons.inventory.services import InventoryService
from addons.loyalty.models import Voucher, VoucherUsage
from addons.orders.models import Order, OrderAddress, OrderItem, OrderValue
from addons.sale_loyalty.models import SaleOrderCoupon
from addons.sale_stock.models import SaleOrderDelivery
from addons.stock.models import StockPicking
from .models import SaleOrder, SaleOrderLine


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
    total de la orden quede en ``0.00`` y no stale con el valor previo.
    """
    if order.state != SaleOrder.STATE_DRAFT:
        raise DraftOrderError('La orden no es un draft.', 'ORDEN_NO_DRAFT')
    order.order_line.all().delete()
    order._compute_amounts()


def _draft_coupon_voucher(order):
    """Voucher del cupón aplicado al draft, o None (H-CART-CL-02)."""
    coupon = SaleOrderCoupon.objects.filter(order=order).first()
    if coupon is None or not coupon.voucher_id:
        return None
    return coupon.voucher


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
        voucher = _draft_coupon_voucher(order)
        if voucher is not None:
            discount = voucher.calculate_discount(subtotal)
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


def apply_voucher_to_draft(order, code, user=None):
    """Aplica un voucher al draft vía ``SaleOrderCoupon`` (UC-CART-04 +
    H-CICLO112-01; cierra H-CART-CL-02 — el ancla deja de ser el string
    ``voucher_code``). El descuento NO se congela aquí —
    ``get_draft_totals`` lo recalcula vivo mientras la orden siga en
    draft. Retorna ``(voucher, discount, cart_total)``.
    """
    if order.state != SaleOrder.STATE_DRAFT:
        raise DraftOrderError('La orden no es un draft.', 'ORDEN_NO_DRAFT')
    voucher = Voucher.objects.filter(code=code).first()
    if voucher is None:
        raise DraftOrderError('El voucher no existe.', 'VOUCHER_NOT_FOUND')

    with transaction.atomic():
        order = SaleOrder.objects.select_for_update().get(pk=order.pk)
        cart_total = sum(
            (l.price_unit * l.product_uom_qty for l in order.order_line.all()),
            Decimal('0.00'))

        error_code = voucher.validate_for_cart(cart_total, user)
        if error_code:
            raise DraftOrderError(f'Voucher no aplicable: {error_code}',
                                  error_code)
        if user is not None and getattr(user, 'is_authenticated', False):
            if VoucherUsage.objects.filter(user=user, voucher=voucher).exists():
                raise DraftOrderError('Ya has utilizado este voucher.',
                                      'VOUCHER_ALREADY_USED')
        if _draft_coupon_voucher(order) is not None:
            raise DraftOrderError(
                'El carrito ya tiene un voucher aplicado. Elimínelo primero.',
                'VOUCHER_ALREADY_APPLIED')

        coupon, _ = SaleOrderCoupon.objects.get_or_create(order=order)
        coupon.voucher = voucher
        coupon.save(update_fields=['voucher', 'updated_at'])

    return voucher, voucher.calculate_discount(cart_total), cart_total


def remove_voucher_from_draft(order):
    """Quita el voucher del draft (elimina el ``SaleOrderCoupon``)."""
    if _draft_coupon_voucher(order) is None:
        raise DraftOrderError('El carrito no tiene voucher aplicado.',
                              'NO_ACTIVE_VOUCHER')
    SaleOrderCoupon.objects.filter(order=order).delete()


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
       + ``OrderItem``/``OrderValue``/``OrderAddress`` que pagos/
       logística/post-venta consumen hasta re-anclarse (V3/V4); la
       ``OrderAddress`` ancla a AMBOS (FK dual de V1). Retorna el espejo
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
    # espejo legacy, cuyos ``OrderItem`` son de producto por contrato.
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
    voucher = _draft_coupon_voucher(order)

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
        # depender del enum monolítico ``Order.status``. Additivo: modelos
        # dormidos, ningún lector vivo depende de ellos todavía.
        picking = StockPicking.objects.create(
            sale_order=order, state=StockPicking.STATE_CONFIRMED)
        picking.action_assign()
        SaleOrderDelivery.objects.get_or_create(
            order=order,
            defaults={'delivery_status': SaleOrderDelivery.STATUS_STARTED},
        )

        # Puente legacy (se retira en V5 — analisis-unificar-orders-sale).
        # I1 (H-API-29, decisión ejecutor 2026-07-28): la identidad pública
        # es la canónica — el espejo nace con order_number = sale.name, así
        # todo el contrato (serializers, emails, lookups) publica ``S-…``
        # sin re-anclar cada sitio. Órdenes previas conservan su ``PY-…``.
        legacy = Order.objects.create(
            sale_order=order,
            order_number=order.name,
            user=order.partner,
            guest_email=(guest_email if (guest_email and not order.partner_id)
                         else None),
            # O2C V5d: sin columna espejo. El PENDING inicial lo produce el
            # estado real de los ejes (venta confirmada + sin pago aprobado).
            notes=order.notes,
            voucher_code=voucher.code if voucher else '',
            voucher_discount=voucher_discount,
        )
        OrderItem.objects.bulk_create([
            OrderItem(
                order=legacy,
                product=line.product,
                variant=line.variant,
                product_name=line.product.name,
                variant_label=(line.variant.option.label if line.variant
                               else ''),
                sku=(line.variant.sku if line.variant else line.product.sku),
                unit_price=line.price_unit,
                quantity=line.product_uom_qty,
                subtotal=line.price_unit * line.product_uom_qty,
            )
            for line in lines
        ])
        OrderValue.objects.create(
            order=legacy, subtotal=subtotal, tax=tax,
            shipping_cost=shipping_cost, discount=voucher_discount,
            total=total,
        )
        OrderAddress.objects.create(order=legacy, sale_order=order,
                                    **address_data)
    return legacy
