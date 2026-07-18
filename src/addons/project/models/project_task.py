"""Modelo ``ProjectTask`` — addon ``project``.

Adaptación de Odoo ``project/models/project_task.py`` (``project.task``): tarea
dentro de un proyecto. Núcleo portable: ``name``/``description``/``priority``/
``active``/``sequence`` + ``project`` (FK) + ``stage`` (FK etapa) + ``state`` +
``date_deadline``. Se omite la maquinaria de horas/timesheets/recurrencia de
Odoo (Clausula 5 — no existe en este stack).
"""
from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class ProjectTask(TimeStampedModel):
    """``project.task`` — tarea de un proyecto."""

    STATE_IN_PROGRESS = 'in_progress'
    STATE_DONE        = 'done'
    STATE_CANCEL      = 'cancel'
    STATE_CHOICES = [
        (STATE_IN_PROGRESS, 'En progreso'),
        (STATE_DONE, 'Terminada'),
        (STATE_CANCEL, 'Cancelada'),
    ]

    PRIORITY_CHOICES = [('0', 'Normal'), ('1', 'Alta')]

    project       = models.ForeignKey(
        'project.Project', on_delete=models.CASCADE, related_name='tasks',
        help_text='Proyecto (Odoo project_id).',
    )
    name          = models.CharField(
        max_length=255, help_text='Título de la tarea (Odoo project.task.name).',
    )
    description   = models.TextField(
        blank=True, default='', help_text='Descripción (Odoo description).',
    )
    priority      = models.CharField(
        max_length=1, choices=PRIORITY_CHOICES, default='0',
        help_text='Prioridad (Odoo priority).',
    )
    active        = models.BooleanField(
        default=True, help_text='Tarea activa (Odoo active).',
    )
    sequence      = models.IntegerField(
        default=10, help_text='Orden (Odoo sequence).',
    )
    stage         = models.ForeignKey(
        'project.ProjectTaskType', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='tasks', help_text='Etapa (Odoo stage_id).',
    )
    state         = models.CharField(
        max_length=16, choices=STATE_CHOICES, default=STATE_IN_PROGRESS,
        help_text='Estado (Odoo state).',
    )
    assignee      = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='project_tasks', help_text='Responsable (Odoo user_ids).',
    )
    date_deadline = models.DateField(
        null=True, blank=True, help_text='Fecha límite (Odoo date_deadline).',
    )

    class Meta:
        db_table = 'project_task'
        ordering = ['project', 'sequence', 'id']
        verbose_name = 'Tarea de proyecto'
        verbose_name_plural = 'Tareas de proyecto'

    def __str__(self) -> str:
        return f'{self.project.name} — {self.name}'

    def is_closed(self) -> bool:
        """True si la tarea está terminada o cancelada (Odoo is_closed)."""
        return self.state in (self.STATE_DONE, self.STATE_CANCEL)
