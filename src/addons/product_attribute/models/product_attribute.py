"""Modelo ``ProductAttribute`` — addon ``product_attribute``.

Adaptación fiel de Odoo ``product.attribute``
(``product/models/product_attribute.py:22-33``, verificado en 18 y 19):
atributo **reutilizable** entre productos (Color, Talla, Material…) —a
diferencia del ``VariantType`` de ``chartsize``, que es por-producto—. Núcleo:
``name``/``create_variant`` (``always``/``dynamic``/``no_variant``, o18:29-31 ≡
o19:24)/``display_type``/``sequence``.
"""
from django.db import models

from core.models import TimeStampedModel


class ProductAttribute(TimeStampedModel):
    """``product.attribute`` — atributo reutilizable entre productos."""

    CREATE_ALWAYS     = 'always'
    CREATE_DYNAMIC    = 'dynamic'
    CREATE_NO_VARIANT = 'no_variant'
    CREATE_CHOICES = [
        (CREATE_ALWAYS, 'Al instante'),
        (CREATE_DYNAMIC, 'Dinámicamente'),
        (CREATE_NO_VARIANT, 'Nunca (no genera variante)'),
    ]

    DISPLAY_RADIO  = 'radio'
    DISPLAY_SELECT = 'select'
    DISPLAY_COLOR  = 'color'
    DISPLAY_CHOICES = [
        (DISPLAY_RADIO, 'Radio'),
        (DISPLAY_SELECT, 'Selección'),
        (DISPLAY_COLOR, 'Color'),
    ]

    name           = models.CharField(
        max_length=100, help_text='Nombre del atributo (Odoo product.attribute.name).',
    )
    create_variant = models.CharField(
        max_length=16, choices=CREATE_CHOICES, default=CREATE_ALWAYS,
        help_text='Cuándo genera variante (Odoo create_variant).',
    )
    display_type   = models.CharField(
        max_length=16, choices=DISPLAY_CHOICES, default=DISPLAY_RADIO,
        help_text='Cómo se muestra (Odoo display_type).',
    )
    sequence       = models.PositiveIntegerField(
        default=10, help_text='Orden (Odoo sequence).',
    )

    class Meta:
        db_table = 'product_attribute'
        ordering = ['sequence', 'id']
        verbose_name = 'Atributo de producto'
        verbose_name_plural = 'Atributos de producto'

    def __str__(self) -> str:
        return self.name
