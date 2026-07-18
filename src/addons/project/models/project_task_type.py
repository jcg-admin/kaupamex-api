"""Modelo ``ProjectTaskType`` — addon ``project``.

Adaptación de Odoo ``project/models/project_task_type.py`` (``project.task.type``):
etapa (columna kanban) de las tareas. Núcleo portable: ``name``/``sequence``/
``fold``/``color``.
"""
from django.db import models

from core.models import TimeStampedModel


class ProjectTaskType(TimeStampedModel):
    """``project.task.type`` — etapa de tareas de proyecto."""

    name     = models.CharField(
        max_length=100, help_text='Nombre de la etapa (Odoo project.task.type.name).',
    )
    sequence = models.IntegerField(
        default=10, help_text='Orden kanban; menor primero (Odoo sequence).',
    )
    fold     = models.BooleanField(
        default=False, help_text='Plegada en el kanban (Odoo fold).',
    )
    color    = models.IntegerField(
        default=0, help_text='Índice de color (Odoo color).',
    )

    class Meta:
        db_table = 'project_task_type'
        ordering = ['sequence', 'name']
        verbose_name = 'Etapa de tarea de proyecto'
        verbose_name_plural = 'Etapas de tarea de proyecto'

    def __str__(self) -> str:
        return self.name
