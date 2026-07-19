"""Modelo ``ProductTemplateAttributeLine`` — addon ``product`` (base del monolito modular).

Adaptación fiel de Odoo ``product.template.attribute.line``
(``product/models/product_template_attribute_line.py:8-39``, verificado en 18 y
19): asocia un **atributo** a un **producto** y declara **qué valores** de ese
atributo aplican a ese producto. Núcleo: ``product_tmpl_id``/``attribute_id``/
``value_ids`` (M2M). Es el eje del que se genera el producto cartesiano de
combinaciones.
"""
import fields
import models

from core.models import TimeStampedModel


class ProductTemplateAttributeLine(TimeStampedModel):
    """``product.template.attribute.line`` — atributo aplicado a un producto."""

    product   = fields.Many2one(
        'catalogue.Product', on_delete=models.CASCADE, related_name='attribute_lines',
        help_text='Producto (Odoo product_tmpl_id).',
    )
    attribute = fields.Many2one(
        'product.ProductAttribute', on_delete=models.PROTECT,
        related_name='template_lines', help_text='Atributo (Odoo attribute_id).',
    )
    values    = fields.Many2many(
        'product.ProductAttributeValue', related_name='template_lines',
        help_text='Valores aplicables a este producto (Odoo value_ids).',
    )
    sequence  = models.PositiveIntegerField(
        default=10, help_text='Orden (Odoo sequence).',
    )

    class Meta:
        db_table = 'product_template_attribute_line'
        ordering = ['sequence', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'attribute'], name='unique_template_attribute',
            ),
        ]
        verbose_name = 'Línea de atributo de producto'
        verbose_name_plural = 'Líneas de atributo de producto'

    def __str__(self) -> str:
        return f'{self.product} / {self.attribute}'
