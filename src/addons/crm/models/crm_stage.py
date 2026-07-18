"""Modelo ``CrmStage`` — addon ``crm``.

Adaptación fiel de Odoo ``crm/models/crm_stage.py`` (``crm.stage``): etapa del
pipeline de oportunidades. Núcleo: ``name``/``sequence``/``is_won``/``fold``/
``color``.
"""
from django.db import models

from core.models import TimeStampedModel


class CrmStage(TimeStampedModel):
    """``crm.stage`` — etapa del pipeline de oportunidades."""

    # Odoo crm.stage.name (crm_stage.py:25, required, translate).
    name     = models.CharField(
        max_length=100, help_text='Nombre de la etapa (Odoo crm.stage.name).',
    )
    # Odoo sequence (crm_stage.py:26, default 1 — menor es mejor).
    sequence = models.IntegerField(
        default=1, help_text='Orden del pipeline; menor primero (Odoo sequence).',
    )
    # Odoo is_won (crm_stage.py:27) — etapa ganada.
    is_won   = models.BooleanField(
        default=False, help_text='Etapa ganada (Odoo is_won).',
    )
    # Odoo fold (crm_stage.py:32) — plegada en el kanban.
    fold     = models.BooleanField(
        default=False, help_text='Plegada en el pipeline (Odoo fold).',
    )
    # Odoo color (crm_stage.py:36).
    color    = models.IntegerField(
        default=0, help_text='Índice de color (Odoo color).',
    )

    class Meta:
        db_table = 'crm_stage'
        ordering = ['sequence', 'name']
        verbose_name = 'Etapa de CRM'
        verbose_name_plural = 'Etapas de CRM'

    def __str__(self) -> str:
        return self.name
