"""Modelo ``ProductCosting`` — addon ``stock_account``.

Adaptación fiel de Odoo ``product.category.property_cost_method`` +
``product.product.standard_price`` (``stock_account/models/product.py``,
verificado en 18 y 19): configuración de costeo del producto.

- ``cost_method`` (``standard``/``fifo``/``average``, o18:962-964) — en Odoo
  vive en ``product.category``; aquí se materializa por producto (este proyecto
  no tiene ``product.category`` con método de costeo, DEC-SALE-01).
- ``standard_price`` — costo unitario. En AVCO es el promedio móvil que
  ``receive`` recalcula; en FIFO refleja el último costo; en estándar es fijo.
"""
from decimal import Decimal

from django.db import models

from core.models import TimeStampedModel


class ProductCosting(TimeStampedModel):
    """``product`` costeo — método + costo unitario (Odoo cost_method + standard_price)."""

    COST_STANDARD = 'standard'
    COST_FIFO     = 'fifo'
    COST_AVERAGE  = 'average'
    COST_CHOICES = [
        (COST_STANDARD, 'Precio estándar'),
        (COST_FIFO, 'Primeras entradas, primeras salidas (FIFO)'),
        (COST_AVERAGE, 'Costo promedio (AVCO)'),
    ]

    product        = models.OneToOneField(
        'catalogue.Product', on_delete=models.CASCADE, related_name='costing',
        help_text='Producto (Odoo product_id).',
    )
    cost_method    = models.CharField(
        max_length=16, choices=COST_CHOICES, default=COST_AVERAGE,
        help_text='Método de costeo (Odoo property_cost_method).',
    )
    standard_price = models.DecimalField(
        max_digits=12, decimal_places=4, default=Decimal('0.0000'),
        help_text='Costo unitario (Odoo standard_price).',
    )

    class Meta:
        db_table = 'stock_account_product_costing'
        verbose_name = 'Costeo de producto'
        verbose_name_plural = 'Costeos de producto'

    def __str__(self) -> str:
        return f'{self.product} [{self.cost_method}] {self.standard_price}'

    @classmethod
    def for_product(cls, product, cost_method=None):
        """Obtiene (o crea) el costeo del producto (Odoo tiene siempre categoría)."""
        costing, _ = cls.objects.get_or_create(product=product)
        if cost_method is not None and costing.cost_method != cost_method:
            costing.cost_method = cost_method
            costing.save(update_fields=['cost_method', 'updated_at'])
        return costing
