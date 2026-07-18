"""Modelo ``StockLandedCostLine`` — addon ``stock_landed_costs``.

Adaptación fiel de Odoo ``stock.landed.cost.lines``
(``stock_landed_costs/models/stock_landed_cost.py:347-367``, verificado en 18 y
19): una componente de coste en destino (p. ej. "Flete", "Aduana") con su
``price_unit`` (monto) y su ``split_method`` — cómo se reparte sobre los
productos: por partes iguales, por cantidad, por costo actual, por peso o por
volumen (o18:12-16).
"""
from decimal import Decimal

from django.db import models

from core.models import TimeStampedModel


class StockLandedCostLine(TimeStampedModel):
    """``stock.landed.cost.lines`` — una componente de coste + su reparto."""

    SPLIT_EQUAL       = 'equal'
    SPLIT_BY_QUANTITY = 'by_quantity'
    SPLIT_BY_COST     = 'by_current_cost_price'
    SPLIT_BY_WEIGHT   = 'by_weight'
    SPLIT_BY_VOLUME   = 'by_volume'
    SPLIT_CHOICES = [
        (SPLIT_EQUAL, 'Igual'),
        (SPLIT_BY_QUANTITY, 'Por cantidad'),
        (SPLIT_BY_COST, 'Por costo actual'),
        (SPLIT_BY_WEIGHT, 'Por peso'),
        (SPLIT_BY_VOLUME, 'Por volumen'),
    ]

    cost         = models.ForeignKey(
        'stock_landed_costs.StockLandedCost', on_delete=models.CASCADE,
        related_name='cost_lines', help_text='Documento (Odoo cost_id).',
    )
    name         = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Descripción de la componente (Odoo name).',
    )
    price_unit   = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Monto del coste (Odoo price_unit).',
    )
    split_method = models.CharField(
        max_length=24, choices=SPLIT_CHOICES, default=SPLIT_BY_QUANTITY,
        help_text='Método de reparto (Odoo split_method).',
    )

    class Meta:
        db_table = 'stock_landed_cost_line'
        ordering = ['id']
        verbose_name = 'Componente de coste en destino'
        verbose_name_plural = 'Componentes de coste en destino'

    def __str__(self) -> str:
        return f'{self.name or self.split_method}: {self.price_unit}'
