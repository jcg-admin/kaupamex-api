"""Modelo ``MrpProductionMove`` — addon ``mrp``.

Puente que materializa ``move_raw_ids``/``move_finished_ids`` de Odoo
(``mrp.production``, o18:175-180). En Odoo esos One2many se apoyan en las FKs
``raw_material_production_id``/``production_id`` que ``mrp`` **inyecta en**
``stock.move``. Django no puede añadir columnas a ``stock.StockMove`` desde otra
app (DEC-SALE-01), así que la relación se materializa aquí: cada movimiento de
la orden (consumo de materia prima o producto terminado) queda ligado con su
``role``.
"""
import fields
import models

from core.models import TimeStampedModel


class MrpProductionMove(TimeStampedModel):
    """Enlace ``mrp.production`` ↔ ``stock.move`` con rol (raw/finished)."""

    ROLE_RAW      = 'raw'
    ROLE_FINISHED = 'finished'
    ROLE_CHOICES = [
        (ROLE_RAW, 'Materia prima (Odoo move_raw_ids)'),
        (ROLE_FINISHED, 'Producto terminado (Odoo move_finished_ids)'),
    ]

    production = fields.Many2one(
        'mrp.MrpProduction', on_delete=models.CASCADE, related_name='production_moves',
        help_text='Orden de fabricación (Odoo production_id).',
    )
    move       = models.OneToOneField(
        'stock.StockMove', on_delete=models.CASCADE, related_name='mrp_production_move',
        help_text='Movimiento de stock ligado.',
    )
    role       = fields.Selection(
        max_length=16, choices=ROLE_CHOICES,
        help_text='raw = move_raw_ids; finished = move_finished_ids.',
    )

    class Meta:
        db_table = 'mrp_production_move'
        ordering = ['id']
        verbose_name = 'Movimiento de orden de fabricación'
        verbose_name_plural = 'Movimientos de orden de fabricación'

    def __str__(self) -> str:
        return f'{self.production} [{self.role}] {self.move}'
