"""Modelo ``SaleOrderCoupon`` — addon ``sale_loyalty``.

Adaptación del módulo Odoo ``sale_loyalty``, que puentea ``sale`` + ``loyalty``
(programas/tarjetas/premios) añadiendo cupones/recompensas a ``sale.order``. Este
e-commerce usa el addon ``voucher`` (códigos de descuento) en vez del módulo
``loyalty`` completo; la contribución de ``sale_loyalty`` se materializa como un
**modelo relacionado** (OneToOne a ``sale.order``) que ata el ``voucher`` aplicado
a la orden — misma forma de módulo-extensión que ``sale_stock``.
"""
from decimal import Decimal

import fields
import models

from addons.base.models import TimeStampedModel
from addons.catalogue.models import Product

# ----------------------------------------------------------------------
# E1-bis — producto de servicio de la línea de recompensa.
#
# Simétrico de ``delivery.ShippingMethod.ensure_service_product()``: en Odoo
# la recompensa de ``sale_loyalty`` es una LÍNEA de precio negativo, y toda
# línea necesita producto. A diferencia del envío —que tiene un producto por
# método— el descuento es **uno solo** para todo el sistema: no hay un
# "método de descuento" que catalogar, así que el producto es global.
#
# ``is_published=False`` ≙ ``sale_ok=False`` de la semilla Odoo: dato maestro
# editable, fuera del storefront.
# ----------------------------------------------------------------------
REWARD_SKU = 'SRV-DESCUENTO'


def ensure_reward_product() -> Product:
    """Devuelve el producto de servicio del descuento, creándolo si falta.

    Idempotente. Precio 0: el importe efectivo lo fija la línea con su
    ``price_unit`` negativo, calculado por el voucher aplicado.
    """
    product, _ = Product.objects.get_or_create(
        sku=REWARD_SKU,
        defaults={
            'name': 'Descuento',
            'slug': 'servicio-descuento',
            'price': Decimal('0.00'),
            'is_active': True,
            'is_published': False,
            'short_description': 'Concepto de descuento para facturación.',
        },
    )
    return product


class SaleOrderCoupon(TimeStampedModel):
    """Cupón aplicado a una ``sale.order`` (paridad ``cart.voucher``)."""

    order   = models.OneToOneField(
        'sale.SaleOrder', on_delete=models.CASCADE, related_name='coupon',
        help_text='Orden de venta (Odoo sale.order).',
    )
    voucher = fields.Many2one(
        'loyalty.Voucher', null=True, blank=True,
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
    #
    # E1-bis — la base es el subtotal de **producto**: se excluyen las líneas
    # marcadoras (``is_delivery``/``is_reward``). Sin esa exclusión el orden en
    # que el llamador materializa las líneas cambiaría el descuento (un
    # PERCENTAGE aplicado después del envío lo incluiría en la base, y la propia
    # línea de recompensa se realimentaría). Preserva la semántica del carrito
    # legacy, donde el descuento se calculaba sobre el subtotal de productos.
    def discount_base(self) -> Decimal:
        lines = self.order.order_line.filter(is_delivery=False, is_reward=False)
        return sum((line.price_subtotal() for line in lines), Decimal('0.00'))

    def discount_amount(self) -> Decimal:
        if not self.voucher_id:
            return Decimal('0.00')
        return self.voucher.calculate_discount(self.discount_base())

    def amount_total_after_discount(self) -> Decimal:
        return self.order.amount_total() - self.discount_amount()
