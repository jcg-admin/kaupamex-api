"""Modelo ``StockLot`` — addon ``stock``.

Adaptación fiel de Odoo ``stock.lot`` (``stock/models/stock_lot.py``, núcleo
idéntico en 18 y 19): un lote / número de serie de un producto. Verificado en
ambas versiones — ``name`` (Lot/Serial Number, requerido, o18:57-59 ≡ o19),
``ref`` (referencia interna, o18:60), ``product_id`` (o18:61-65),
``quant_ids`` (One2many inverso, o18:69) y ``product_qty`` (a la mano,
compute sobre los quants del lote, o18:70).

Es la **base** que ``product_expiry`` extiende con fechas de caducidad y la
estrategia de remoción FEFO (DEC-SALE-01: la extensión ``_inherit`` de Odoo se
adapta como modelo RELATED en el addon satélite).
"""
from decimal import Decimal

import fields
import models

from addons.base.models import TimeStampedModel


class StockLot(TimeStampedModel):
    """``stock.lot`` — lote / número de serie de un producto."""

    name       = fields.Char(
        max_length=120,
        help_text='Número de lote / serie (Odoo stock.lot.name, requerido).',
    )
    ref        = fields.Char(
        max_length=120, blank=True, default='',
        help_text='Referencia interna (Odoo stock.lot.ref).',
    )
    product    = fields.Many2one(
        'product.ProductProduct', on_delete=models.CASCADE, related_name='lots',
        help_text='Producto (Odoo product_id).',
    )

    class Meta:
        db_table = 'stock_lot'
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'name'], name='unique_lot_product_name',
            ),
        ]
        ordering = ['name', 'id']
        verbose_name = 'Lote / número de serie'
        verbose_name_plural = 'Lotes / números de serie'

    def __str__(self) -> str:
        return f'{self.name} ({self.product})'

    @property
    def product_qty(self) -> Decimal:
        """Cantidad a la mano del lote (Odoo ``product_qty``, compute sobre quants).

        Suma la cantidad de todos los ``stock.quant`` de este lote. Réplica de
        ``_product_qty`` de Odoo (que agrega ``quant_ids.quantity``).
        """
        total = self.quants.aggregate(s=models.Sum('quantity'))['s']
        return total if total is not None else Decimal('0.00')
