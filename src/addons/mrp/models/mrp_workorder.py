"""Modelo ``MrpWorkorder`` — addon ``mrp``.

Adaptación fiel de Odoo ``mrp.workorder`` (``mrp/models/mrp_workorder.py``,
verificado en 18 y 19): una **orden de trabajo** — la ejecución de una operación
de la hoja de ruta dentro de una orden de fabricación. Núcleo —
``production_id``/``workcenter_id``/``operation_id``/``duration`` (minutos
reales, o18:90)/``duration_expected`` (o18:87)/``state``. El ``duration`` × el
``costs_hour`` del centro es el costo de mano de obra imputado al terminado.
"""
from decimal import Decimal

import fields
import models

from core.models import TimeStampedModel


class MrpWorkorder(TimeStampedModel):
    """``mrp.workorder`` — una orden de trabajo."""

    STATE_PENDING  = 'pending'
    STATE_PROGRESS = 'progress'
    STATE_DONE     = 'done'
    STATE_CANCEL   = 'cancel'
    STATE_CHOICES = [
        (STATE_PENDING, 'Pendiente'),
        (STATE_PROGRESS, 'En progreso'),
        (STATE_DONE, 'Terminada'),
        (STATE_CANCEL, 'Cancelada'),
    ]

    name              = fields.Char(
        max_length=100, blank=True, default='',
        help_text='Descripción (Odoo mrp.workorder.name).',
    )
    production        = fields.Many2one(
        'mrp.MrpProduction', on_delete=models.CASCADE, related_name='workorders',
        help_text='Orden de fabricación (Odoo production_id).',
    )
    workcenter        = fields.Many2one(
        'mrp.MrpWorkcenter', on_delete=models.PROTECT, related_name='workorders',
        help_text='Centro de trabajo (Odoo workcenter_id).',
    )
    operation         = fields.Many2one(
        'mrp.MrpRoutingWorkcenter', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='workorders', help_text='Operación (Odoo operation_id).',
    )
    duration_expected = fields.Monetary(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Duración esperada en minutos (Odoo duration_expected).',
    )
    duration          = fields.Monetary(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Duración real en minutos (Odoo duration).',
    )
    state             = fields.Selection(
        max_length=16, choices=STATE_CHOICES, default=STATE_PENDING,
        help_text='Estado (Odoo mrp.workorder.state).',
    )

    class Meta:
        db_table = 'mrp_workorder'
        ordering = ['id']
        verbose_name = 'Orden de trabajo'
        verbose_name_plural = 'Órdenes de trabajo'

    def __str__(self) -> str:
        return self.name or f'WO/{self.pk}'

    def labor_cost(self) -> Decimal:
        """Costo de mano de obra = (duración real / 60) × costo por hora (Odoo)."""
        hours = self.duration / Decimal('60')
        return (hours * self.workcenter.costs_hour).quantize(Decimal('0.01'))
