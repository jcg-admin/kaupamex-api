"""Modelo ``SaleOrderTemplateLine`` — addon ``sale_management``.

Adaptación fiel de ``sale.order.template.line``: una línea de la plantilla de
cotización (producto + cantidad, o una sección/nota). Al aplicar la plantilla a
una ``sale.order`` estas líneas se materializan en ``sale.order.line``.
"""
from decimal import Decimal

from django.db import models

from core.models import TimeStampedModel


class SaleOrderTemplateLine(TimeStampedModel):
    """``sale.order.template.line`` — línea de plantilla de cotización."""

    # Odoo display_type (sale_order_template_line.py:57): línea de producto vs
    # sección/nota (line_section/line_note).
    DISPLAY_PRODUCT = ''
    DISPLAY_SECTION = 'line_section'
    DISPLAY_NOTE    = 'line_note'
    DISPLAY_TYPES = [
        (DISPLAY_PRODUCT, 'Producto'),
        (DISPLAY_SECTION, 'Sección'),
        (DISPLAY_NOTE,    'Nota'),
    ]

    template        = models.ForeignKey(
        'sale_management.SaleOrderTemplate', on_delete=models.CASCADE,
        related_name='template_line',
        help_text='Plantilla (Odoo sale_order_template_id).',
    )
    sequence        = models.IntegerField(
        default=10, help_text='Orden dentro de la plantilla (Odoo sequence).',
    )
    product         = models.ForeignKey(
        'catalogue.Product', null=True, blank=True, on_delete=models.PROTECT,
        related_name='sale_template_lines',
        help_text='Producto (Odoo product_id); NULL en sección/nota.',
    )
    name            = models.TextField(
        blank=True, default='',
        help_text='Descripción de la línea (Odoo name).',
    )
    product_uom_qty = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('1.00'),
        help_text='Cantidad (Odoo product_uom_qty).',
    )
    display_type    = models.CharField(
        max_length=12, choices=DISPLAY_TYPES, default=DISPLAY_PRODUCT, blank=True,
        help_text='Tipo de línea: producto/sección/nota (Odoo display_type).',
    )

    class Meta:
        db_table = 'sale_order_template_line'
        ordering = ['template', 'sequence']
        verbose_name = 'Línea de plantilla de cotización'
        verbose_name_plural = 'Líneas de plantilla de cotización'

    def __str__(self) -> str:
        return self.name or (str(self.product) if self.product_id else self.display_type)
