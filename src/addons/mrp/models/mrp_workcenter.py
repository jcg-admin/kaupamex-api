"""Modelo ``MrpWorkcenter`` — addon ``mrp``.

Adaptación fiel de Odoo ``mrp.workcenter`` (``mrp/models/mrp_workcenter.py``,
verificado en 18 y 19): centro de trabajo. Núcleo — ``name``/``costs_hour``
(costo por hora, o18:44 ≡ o19:41)/``time_efficiency`` (o18:30). El
``costs_hour`` es la base del **costo de mano de obra** que la orden de
fabricación imputa al producto terminado.
"""
from decimal import Decimal

import fields
import models

from core.models import TimeStampedModel


class MrpWorkcenter(TimeStampedModel):
    """``mrp.workcenter`` — centro de trabajo."""

    name            = fields.Char(
        max_length=100, help_text='Nombre (Odoo mrp.workcenter.name).',
    )
    costs_hour      = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Costo por hora (Odoo costs_hour).',
    )
    time_efficiency = fields.Monetary(
        max_digits=6, decimal_places=2, default=Decimal('100.00'),
        help_text='Eficiencia de tiempo % (Odoo time_efficiency).',
    )
    capacity        = fields.Monetary(
        max_digits=8, decimal_places=2, default=Decimal('1.00'),
        help_text='Capacidad por defecto (Odoo default_capacity).',
    )

    class Meta:
        db_table = 'mrp_workcenter'
        ordering = ['name']
        verbose_name = 'Centro de trabajo'
        verbose_name_plural = 'Centros de trabajo'

    def __str__(self) -> str:
        return self.name
