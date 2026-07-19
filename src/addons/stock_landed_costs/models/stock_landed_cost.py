"""Modelo ``StockLandedCost`` — addon ``stock_landed_costs``.

Adaptación fiel de Odoo ``stock.landed.cost``
(``stock_landed_costs/models/stock_landed_cost.py:20-72``, verificado en 18 y
19): documento de **costes en destino** (fletes, aranceles, seguros) que se
reparten sobre los productos de una recepción y se **suman a su costo unitario**
de inventario. Es lo que hace rastreable el *costo unitario real de entrega*:
el costo del producto deja de ser solo el precio de compra y absorbe el flete.
"""
from decimal import Decimal

import fields
import models

from core.models import TimeStampedModel


class StockLandedCost(TimeStampedModel):
    """``stock.landed.cost`` — documento de costes en destino."""

    STATE_DRAFT  = 'draft'
    STATE_DONE   = 'done'
    STATE_CANCEL = 'cancel'
    STATE_CHOICES = [
        (STATE_DRAFT, 'Borrador'),
        (STATE_DONE, 'Validado'),
        (STATE_CANCEL, 'Cancelado'),
    ]

    name  = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Referencia (Odoo stock.landed.cost.name).',
    )
    state = fields.Selection(
        max_length=16, choices=STATE_CHOICES, default=STATE_DRAFT,
        help_text='Estado (Odoo stock.landed.cost.state).',
    )

    class Meta:
        db_table = 'stock_landed_cost'
        ordering = ['-created_at', '-id']
        verbose_name = 'Coste en destino'
        verbose_name_plural = 'Costes en destino'

    def __str__(self) -> str:
        return self.name or f'LC/{self.pk}'

    def amount_total(self) -> Decimal:
        """Suma de las líneas de coste (Odoo amount_total)."""
        total = Decimal('0.00')
        for line in self.cost_lines.all():
            total += line.price_unit
        return total
