"""Modelo ``PurchaseOrderLine`` — addon ``purchase``.

Adaptación fiel de Odoo ``purchase.order.line`` (``purchase/models/
purchase_order_line.py``, idéntico en 18 y 19): línea de una orden de compra.
Núcleo verificado en ambas versiones — ``name``/``product_qty``/``price_unit``/
``discount``/``product_id``/``order_id`` + ``price_subtotal`` computado. Espeja el
desglose por línea de ``sale.order.line`` (IVA-incluido MX) para consistencia.
"""
from decimal import Decimal

from django.core.validators import MinValueValidator
import fields
import models

from addons.settings_app.models import SiteSettings
from core.models import TimeStampedModel


class PurchaseOrderLine(TimeStampedModel):
    """``purchase.order.line`` — una línea de la orden de compra."""

    order       = fields.Many2one(
        'purchase.PurchaseOrder', on_delete=models.CASCADE, related_name='order_line',
        help_text='Odoo order_id.',
    )
    product     = fields.Many2one(
        'catalogue.Product', on_delete=models.PROTECT,
        related_name='purchase_order_lines', help_text='Odoo product_id.',
    )
    name        = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Descripción de la línea (Odoo purchase.order.line.name).',
    )
    product_qty = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)],
        help_text='Cantidad (Odoo product_qty).',
    )
    price_unit  = fields.Monetary(
        max_digits=12, decimal_places=2, help_text='Odoo price_unit (IVA incl.).',
    )
    discount    = fields.Monetary(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Descuento % de la línea (Odoo discount).',
    )

    class Meta:
        db_table = 'purchase_order_line'
        verbose_name = 'Línea de orden de compra'
        verbose_name_plural = 'Líneas de orden de compra'

    def __str__(self) -> str:
        return f'{self.name or self.product} ×{self.product_qty}'

    # Desglose por línea — espeja sale.order.line (Odoo _compute_amount).
    def price_total(self) -> Decimal:
        gross = (self.price_unit * self.product_qty
                 * (Decimal('1') - self.discount / Decimal('100')))
        return gross.quantize(Decimal('0.01'))

    def price_tax(self) -> Decimal:
        rate = SiteSettings.get_current().iva_rate
        return (self.price_total() * rate / (1 + rate)).quantize(Decimal('0.01'))

    def price_subtotal(self) -> Decimal:
        return self.price_total() - self.price_tax()
