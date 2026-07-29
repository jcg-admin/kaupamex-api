"""Servicios de cupón sobre el draft — addon ``sale_loyalty``.

Portados desde ``sale/services.py`` (T-034). En la referencia el cupón es
territorio de ``sale_loyalty`` (``depends: sale, loyalty``), no del núcleo:
``sale`` no sabe que existen los cupones. Aquí ocurría al revés — el núcleo
importaba ``SaleOrderCoupon`` y resolvía la aplicación del voucher, una de
las aristas núcleo→satélite del ciclo de imports (H-API-49).

La dirección ahora es la de la referencia: este módulo importa ``sale``
(satélite → núcleo), nunca al revés.
"""
from decimal import Decimal

from django.db import transaction

from addons.loyalty.models import Voucher, VoucherUsage
from addons.sale.models import SaleOrder
from addons.sale.services import DraftOrderError
from addons.sale_loyalty.models import SaleOrderCoupon


def draft_coupon_voucher(order):
    """Voucher del cupón aplicado al draft, o ``None`` (H-CART-CL-02)."""
    coupon = SaleOrderCoupon.objects.filter(order=order).first()
    if coupon is None or not coupon.voucher_id:
        return None
    return coupon.voucher


def draft_coupon_discount(order, subtotal):
    """Descuento vivo del cupón sobre ``subtotal``; ``0.00`` si no hay.

    Lo consume el receptor de ``draft_discount_requested`` para que
    ``get_draft_totals`` obtenga el descuento sin conocer el cupón.
    """
    voucher = draft_coupon_voucher(order)
    if voucher is None:
        return Decimal('0.00')
    return voucher.calculate_discount(subtotal)


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
        if draft_coupon_voucher(order) is not None:
            raise DraftOrderError(
                'El carrito ya tiene un voucher aplicado. Elimínelo primero.',
                'VOUCHER_ALREADY_APPLIED')

        coupon, _ = SaleOrderCoupon.objects.get_or_create(order=order)
        coupon.voucher = voucher
        coupon.save(update_fields=['voucher', 'updated_at'])

    return voucher, voucher.calculate_discount(cart_total), cart_total


def remove_voucher_from_draft(order):
    """Quita el voucher del draft (elimina el ``SaleOrderCoupon``)."""
    if draft_coupon_voucher(order) is None:
        raise DraftOrderError('El carrito no tiene voucher aplicado.',
                              'NO_ACTIVE_VOUCHER')
    SaleOrderCoupon.objects.filter(order=order).delete()
