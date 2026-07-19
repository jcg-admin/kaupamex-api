"""Modelo ``ProductAttributeValue`` — addon ``product`` (base del monolito modular).

Adaptación fiel de Odoo ``product.attribute.value``
(``product/models/product_attribute_value.py``, verificado en 18 y 19): un valor
posible de un atributo reutilizable (p. ej. del atributo Color: Rojo, Azul).
Núcleo: ``name``/``attribute_id``/``sequence``.
"""
import fields
import models

from core.models import TimeStampedModel


class ProductAttributeValue(TimeStampedModel):
    """``product.attribute.value`` — un valor de un atributo reutilizable."""

    attribute = fields.Many2one(
        'product.ProductAttribute', on_delete=models.CASCADE,
        related_name='values', help_text='Atributo (Odoo attribute_id).',
    )
    name      = fields.Char(
        max_length=100, help_text='Valor (Odoo product.attribute.value.name).',
    )
    sequence  = models.PositiveIntegerField(
        default=10, help_text='Orden (Odoo sequence).',
    )

    class Meta:
        db_table = 'product_attribute_value'
        ordering = ['sequence', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['attribute', 'name'], name='unique_attribute_value_name',
            ),
        ]
        verbose_name = 'Valor de atributo'
        verbose_name_plural = 'Valores de atributo'

    def __str__(self) -> str:
        return f'{self.attribute.name}: {self.name}'
