"""Modelo ``MrpRoutingWorkcenter`` — addon ``mrp``.

Adaptación fiel de Odoo ``mrp.routing.workcenter``
(``mrp/models/mrp_routing.py:14-45``, verificado en 18 y 19): una **operación**
de la hoja de ruta (routing) — qué centro de trabajo la ejecuta y cuánto dura.
Núcleo — ``name`` (operación)/``workcenter_id``/``bom_id``/``time_cycle_manual``
(duración en minutos). El tiempo × el ``costs_hour`` del centro da el costo de
la operación.
"""
from decimal import Decimal

from django.db import models

from core.models import TimeStampedModel


class MrpRoutingWorkcenter(TimeStampedModel):
    """``mrp.routing.workcenter`` — una operación de la hoja de ruta."""

    name          = models.CharField(
        max_length=100, help_text='Operación (Odoo mrp.routing.workcenter.name).',
    )
    bom           = models.ForeignKey(
        'mrp.MrpBom', null=True, blank=True, on_delete=models.CASCADE,
        related_name='operations', help_text='BoM (Odoo bom_id).',
    )
    workcenter    = models.ForeignKey(
        'mrp.MrpWorkcenter', on_delete=models.PROTECT, related_name='operations',
        help_text='Centro de trabajo (Odoo workcenter_id).',
    )
    time_cycle    = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Duración en minutos (Odoo time_cycle_manual).',
    )
    sequence      = models.PositiveIntegerField(
        default=10, help_text='Orden de la operación (Odoo sequence).',
    )

    class Meta:
        db_table = 'mrp_routing_workcenter'
        ordering = ['sequence', 'id']
        verbose_name = 'Operación de hoja de ruta'
        verbose_name_plural = 'Operaciones de hoja de ruta'

    def __str__(self) -> str:
        return f'{self.name} @ {self.workcenter}'
