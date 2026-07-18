"""Modelo ``ProductTemplateAttributeValue`` — addon ``product_attribute``.

Adaptación fiel de Odoo ``product.template.attribute.value``
(``product/models/product_template_attribute_value.py:10-35``, verificado en 18
y 19): el valor de un atributo **para un producto concreto**, con su
``price_extra`` (sobreprecio o18:35 ≡ o19:35). Es la pieza que hace que una
opción (p. ej. talla XL) cueste ``+50`` sobre el precio base — lo que el
``chartsize`` original no modelaba de forma reutilizable.
"""
from decimal import Decimal

from django.db import models

from core.models import TimeStampedModel


class ProductTemplateAttributeValue(TimeStampedModel):
    """``product.template.attribute.value`` — valor por-producto con price_extra."""

    line            = models.ForeignKey(
        'product_attribute.ProductTemplateAttributeLine', on_delete=models.CASCADE,
        related_name='template_values', help_text='Línea (Odoo attribute_line_id).',
    )
    attribute_value = models.ForeignKey(
        'product_attribute.ProductAttributeValue', on_delete=models.PROTECT,
        related_name='template_values',
        help_text='Valor del atributo (Odoo product_attribute_value_id).',
    )
    price_extra     = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Sobreprecio de esta opción (Odoo price_extra).',
    )

    class Meta:
        db_table = 'product_template_attribute_value'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['line', 'attribute_value'],
                name='unique_template_attribute_value',
            ),
        ]
        verbose_name = 'Valor de atributo por producto'
        verbose_name_plural = 'Valores de atributo por producto'

    def __str__(self) -> str:
        extra = f' (+{self.price_extra})' if self.price_extra else ''
        return f'{self.attribute_value.name}{extra}'
