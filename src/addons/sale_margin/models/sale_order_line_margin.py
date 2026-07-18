"""Modelo ``SaleOrderLineMargin`` — addon ``sale_margin``.

Adaptación fiel de Odoo ``sale_margin``, que **extiende** ``sale.order.line`` con
``purchase_price`` (costo) + ``margin``/``margin_percent`` computados. Como
módulo-extensión (DEC-SALE-01), en Django es una app propia con **modelo
relacionado** (OneToOne a ``sale.order.line``).

Odoo ``sale_margin/models/sale_order_line.py``:
- ``purchase_price`` (:15) — costo, snapshot al vender (Odoo lo toma de
  ``product.standard_price``; aquí de ``catalogue.Product.cost``).
- ``margin`` = ``price_subtotal - purchase_price * product_uom_qty`` (:38).
- ``margin_percent`` = ``margin / price_subtotal``.
"""
from decimal import Decimal

from django.db import models

from core.models import TimeStampedModel


class SaleOrderLineMargin(TimeStampedModel):
    """Extensión ``sale_margin`` de ``sale.order.line`` — costo y margen."""

    line          = models.OneToOneField(
        'sale.SaleOrderLine', on_delete=models.CASCADE, related_name='margin',
        help_text='Línea de orden extendida (Odoo sale.order.line).',
    )
    # Odoo purchase_price (sale_margin/…/sale_order_line.py:15) — costo snapshot.
    purchase_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Costo unitario snapshot al vender (Odoo purchase_price).',
    )

    class Meta:
        db_table = 'sale_order_line_margin'
        verbose_name = 'Margen de línea de orden'
        verbose_name_plural = 'Márgenes de líneas de orden'

    def __str__(self) -> str:
        return f'{self.line} → margen {self.margin()}'

    def _cost_snapshot(self) -> Decimal:
        """Costo a usar: snapshot si existe, si no el costo actual del producto."""
        if self.purchase_price is not None:
            return self.purchase_price
        prod = self.line.product
        return prod.cost if prod and prod.cost is not None else Decimal('0.00')

    def capture_purchase_price(self):
        """Congela el costo actual del producto como snapshot (al confirmar)."""
        self.purchase_price = self._cost_snapshot()
        self.save(update_fields=['purchase_price', 'updated_at'])
        return self.purchase_price

    # margin = price_subtotal - purchase_price * qty (Odoo _compute_margin).
    def margin(self) -> Decimal:
        cost_total = self._cost_snapshot() * self.line.product_uom_qty
        return (self.line.price_subtotal() - cost_total).quantize(Decimal('0.01'))

    # margin_percent = margin / price_subtotal (0 si subtotal 0).
    def margin_percent(self) -> Decimal:
        subtotal = self.line.price_subtotal()
        if subtotal == 0:
            return Decimal('0.00')
        return (self.margin() / subtotal * 100).quantize(Decimal('0.01'))
