"""Modelo ``SaleOrderLineDelivery`` — addon ``sale_stock``.

Extensión ``sale_stock`` de ``sale.order.line`` (Odoo ``_inherit``): cantidad
entregada por línea. Como modelo relacionado (OneToOne a ``sale.order.line``),
la forma Django correcta de un módulo-extensión Odoo separado.

``qty_delivered`` (Odoo ``sale.order.line.qty_delivered``, sale_order_line.py:230;
en Odoo lo computa ``sale_stock`` desde ``stock.move``). Aquí la fuente es
``logistics``/``inventory`` (pickings).
"""
from django.db import models

from core.models import TimeStampedModel


class SaleOrderLineDelivery(TimeStampedModel):
    """Extensión ``sale_stock`` de ``sale.order.line`` — cantidad entregada."""

    line          = models.OneToOneField(
        'sale.SaleOrderLine', on_delete=models.CASCADE, related_name='delivery',
        help_text='Línea de orden extendida (Odoo sale.order.line).',
    )
    qty_delivered = models.PositiveIntegerField(
        default=0,
        help_text='Cantidad entregada (Odoo sale.order.line.qty_delivered).',
    )

    class Meta:
        db_table = 'sale_order_line_delivery'
        verbose_name = 'Entrega de línea de orden'
        verbose_name_plural = 'Entregas de líneas de orden'

    def __str__(self) -> str:
        return f'{self.line} → entregado {self.qty_delivered}'

    # Odoo sale.order.line.qty_to_deliver (sale_stock/…/sale_order_line.py:24).
    def qty_to_deliver(self) -> int:
        return max(self.line.product_uom_qty - self.qty_delivered, 0)
