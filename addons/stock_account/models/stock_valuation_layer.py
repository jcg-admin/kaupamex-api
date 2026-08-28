"""Modelo ``StockValuationLayer`` — addon ``stock_account``.

Adaptación fiel de Odoo ``stock.valuation.layer``
(``stock_account/models/stock_valuation_layer.py``, o18:22-39): capa de
valoración — el libro mayor del valor de inventario. Cada capa registra una
entrada (positiva) o salida (negativa) valuada, con su ``unit_cost``/``value``
y — para FIFO — el saldo ``remaining_qty``/``remaining_value`` que las salidas
consumen. Es la fuente del **costo unitario real de entrega**: cada salida
graba el ``unit_cost`` con el que se valuó ese movimiento.

.. warning::

   **19 retiró este modelo, y 19 gobierna.** Este archivo se portó de
   ``odoo18c``; ``odoo19c`` no lo declara —0 apariciones de
   ``stock.valuation.layer`` en su árbol— porque el saldo FIFO pasó a vivir
   en ``stock.move``. El addon SÍ existe en 19c, con 16 archivos que aquí
   faltan, así que su ausencia no es un hueco de la referencia: es la forma
   que 19 eligió. Se conserva mientras el porte de esos 16 no lo reemplace.

   Su hermano ``product_costing.py`` es peor: no existe en **ninguna** de las
   cuatro raíces medidas — es invención nuestra. Ver :ref:`h-api-889`
   (decisión del ejecutor: 19 gobierna) y la tarea #151.
"""
from decimal import Decimal

import fields
import models

from addons.base.models import TimeStampedModel


class StockValuationLayer(TimeStampedModel):
    """``stock.valuation.layer`` — una capa de valoración de inventario."""

    product_id      = fields.Many2one(
        'product.ProductProduct', on_delete=models.CASCADE, related_name='valuation_layers',
        help_text='Producto (Odoo product_id).',
        db_column='product_id',
    )
    quantity        = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Cantidad valuada; negativa en salidas (Odoo quantity).',
    )
    unit_cost       = fields.Monetary(
        max_digits=12, decimal_places=4, default=Decimal('0.0000'),
        help_text='Valor unitario del movimiento (Odoo unit_cost).',
    )
    value           = fields.Monetary(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Valor total; negativo en salidas (Odoo value).',
    )
    remaining_qty   = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Saldo por consumir en FIFO (Odoo remaining_qty).',
    )
    remaining_value = fields.Monetary(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Valor del saldo FIFO (Odoo remaining_value).',
    )
    stock_move_id   = fields.Many2one(
        'stock.StockMove', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='valuation_layers', help_text='Movimiento (Odoo stock_move_id).',
        db_column='stock_move_id',
    )
    description     = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Descripción (Odoo description).',
    )

    class Meta:
        db_table = 'stock_valuation_layer'
        ordering = ['id']
        verbose_name = 'Capa de valoración de inventario'
        verbose_name_plural = 'Capas de valoración de inventario'

    def __str__(self) -> str:
        return f'{self.product_id} {self.quantity}@{self.unit_cost} = {self.value}'
