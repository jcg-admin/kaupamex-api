"""Modelo ``StockValuationAdjustment`` — addon ``stock_landed_costs``.

Adaptación fiel de Odoo ``stock.valuation.adjustment.lines``
(``stock_landed_costs/models/stock_landed_cost.py:378-406``, verificado en 18 y
19): la línea de ajuste — por cada (componente de coste × movimiento objetivo)
guarda ``quantity``/``weight``/``volume``/``former_cost`` (base del reparto) y
el ``additional_landed_cost`` repartido; ``final_cost = former_cost +
additional_landed_cost`` es el nuevo costo del inventario recibido.
"""
from decimal import Decimal

import fields
import models

from addons.base.models import TimeStampedModel


class StockValuationAdjustment(TimeStampedModel):
    """``stock.valuation.adjustment.lines`` — un ajuste de valoración."""

    cost                   = fields.Many2one(
        'stock_landed_costs.StockLandedCost', on_delete=models.CASCADE,
        related_name='adjustment_lines', help_text='Documento (Odoo cost_id).',
    )
    cost_line              = fields.Many2one(
        'stock_landed_costs.StockLandedCostLine', on_delete=models.CASCADE,
        related_name='adjustment_lines', help_text='Componente (Odoo cost_line_id).',
    )
    move                   = fields.Many2one(
        'stock.StockMove', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='landed_cost_adjustments', help_text='Movimiento (Odoo move_id).',
    )
    product                = fields.Many2one(
        'product.ProductProduct', on_delete=models.CASCADE,
        related_name='landed_cost_adjustments', help_text='Producto (Odoo product_id).',
    )
    quantity               = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Cantidad recibida (Odoo quantity).',
    )
    weight                 = fields.Monetary(
        max_digits=12, decimal_places=3, default=Decimal('0.000'),
        help_text='Peso total (Odoo weight).',
    )
    volume                 = fields.Monetary(
        max_digits=12, decimal_places=3, default=Decimal('0.000'),
        help_text='Volumen total (Odoo volume).',
    )
    former_cost            = fields.Monetary(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Costo antes del ajuste (Odoo former_cost).',
    )
    additional_landed_cost = fields.Monetary(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Coste en destino repartido (Odoo additional_landed_cost).',
    )
    final_cost             = fields.Monetary(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Costo final = former + additional (Odoo final_cost).',
    )

    class Meta:
        db_table = 'stock_valuation_adjustment'
        ordering = ['id']
        verbose_name = 'Ajuste de valoración por coste en destino'
        verbose_name_plural = 'Ajustes de valoración por coste en destino'

    def __str__(self) -> str:
        return f'{self.product}: {self.former_cost} + {self.additional_landed_cost}'
