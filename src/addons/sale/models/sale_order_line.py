"""Modelo ``SaleOrderLine`` — addon ``sale``.

Adaptación fiel de Odoo ``sale.order.line`` (``sale/models/sale_order_line.py``):
``product_id``/``product_uom_qty``/``price_unit``/``discount`` +
``price_subtotal``/``price_tax``/``price_total`` computados y **redondeados por
línea** (``_compute_amount``, sale_order_line.py:852). Precios IVA-incluido (MX):
el total de línea es ``price_unit*qty*(1-discount/100)`` y el IVA se extrae con la
tasa vigente, cuantizando por línea (equivale a ``_round_base_lines_tax_details``).
"""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from core.models import TimeStampedModel
from addons.settings_app.models import SiteSettings


class SaleOrderLine(TimeStampedModel):
    """``sale.order.line`` — una línea de la orden/carrito."""

    order           = models.ForeignKey(
        'sale.SaleOrder', on_delete=models.CASCADE, related_name='order_line',
        help_text='Odoo order_id.',
    )
    product         = models.ForeignKey(
        'catalogue.Product', on_delete=models.PROTECT,
        related_name='sale_order_lines', help_text='Odoo product_id.',
    )
    variant         = models.ForeignKey(
        'chartsize.ProductVariant', null=True, blank=True,
        on_delete=models.PROTECT, related_name='sale_order_lines',
    )
    name            = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Descripción de la línea (Odoo name).',
    )
    product_uom_qty = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)],
        help_text='Cantidad (Odoo product_uom_qty).',
    )
    price_unit      = models.DecimalField(
        max_digits=12, decimal_places=2, help_text='Odoo price_unit (IVA incl.).',
    )
    discount        = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Descuento % de la línea (Odoo discount).',
    )

    class Meta:
        db_table     = 'sale_order_line'
        verbose_name = 'Línea de orden de venta'

    def __str__(self):
        return f'{self.name or self.product_id} ×{self.product_uom_qty}'

    # Desglose por línea — de sale.order.line._compute_amount (sale_order_line.py:852).
    def price_total(self) -> Decimal:
        gross = (self.price_unit * self.product_uom_qty
                 * (Decimal('1') - self.discount / Decimal('100')))
        return gross.quantize(Decimal('0.01'))

    def price_tax(self) -> Decimal:
        rate = SiteSettings.get_current().iva_rate
        return (self.price_total() * rate / (1 + rate)).quantize(Decimal('0.01'))

    def price_subtotal(self) -> Decimal:
        return self.price_total() - self.price_tax()
