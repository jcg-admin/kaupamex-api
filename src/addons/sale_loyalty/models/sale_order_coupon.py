"""Modelo ``SaleOrderCoupon`` — addon ``sale_loyalty``.

Adaptación del módulo Odoo ``sale_loyalty``, que puentea ``sale`` + ``loyalty``
(programas/tarjetas/premios) añadiendo cupones/recompensas a ``sale.order``. Este
e-commerce usa el addon ``voucher`` (códigos de descuento) en vez del módulo
``loyalty`` completo; la contribución de ``sale_loyalty`` se materializa como un
**modelo relacionado** (OneToOne a ``sale.order``) que ata el ``voucher`` aplicado
a la orden — misma forma de módulo-extensión que ``sale_stock``.
"""
from decimal import Decimal

from django.db import models

from core.models import TimeStampedModel


class SaleOrderCoupon(TimeStampedModel):
    """Cupón aplicado a una ``sale.order`` (paridad ``cart.voucher``)."""

    order   = models.OneToOneField(
        'sale.SaleOrder', on_delete=models.CASCADE, related_name='coupon',
        help_text='Orden de venta (Odoo sale.order).',
    )
    voucher = models.ForeignKey(
        'voucher.Voucher', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='sale_order_coupons',
        help_text='Cupón aplicado (Odoo sale_loyalty coupon; = cart.voucher).',
    )

    class Meta:
        db_table = 'sale_order_coupon'
        verbose_name = 'Cupón de orden de venta'
        verbose_name_plural = 'Cupones de órdenes de venta'

    def __str__(self) -> str:
        return f'{self.order} → {self.voucher.code if self.voucher_id else "sin cupón"}'

    # Descuento del cupón sobre la orden. Reutiliza Voucher.calculate_discount
    # (voucher/models.py:154) igual que cart.get_discount (cart/models.py:61);
    # FREE_SHIPPING retorna 0 (descuenta en el envío, no en el subtotal).
    def discount_amount(self) -> Decimal:
        if not self.voucher_id:
            return Decimal('0.00')
        return self.voucher.calculate_discount(self.order.amount_untaxed())

    def amount_total_after_discount(self) -> Decimal:
        return self.order.amount_total() - self.discount_amount()
