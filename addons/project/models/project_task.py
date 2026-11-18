"""Modelo ``ProjectTask`` — addon ``project``.

Adaptación de Odoo ``project/models/project_task.py`` (``project.task``): tarea
dentro de un proyecto. Núcleo portable: ``name``/``description``/``priority``/
``active``/``sequence`` + ``project`` (FK) + ``stage`` (FK etapa) + ``state`` +
``date_deadline``. Se omite la maquinaria de horas/timesheets/recurrencia de
Odoo (Clausula 5 — no existe en este stack).
"""

from django.conf import settings
import fields
import models

from addons.base.models import TimeStampedModel


class ProjectTask(models.BaseModel, TimeStampedModel):
    """``project.task`` — tarea de un proyecto."""

    #: Atributos de clase de ``project.task``, verbatim
    #: (``odoo19c: addons/project/models/project_task.py:91-107``).
    #: ``_inherit`` es aquí metadato, como en ``project.project``.
    _name = 'project.task'
    _description = "Task"
    _date_name = "date_assign"
    _inherit = [
        'portal.mixin',
        'mail.thread.cc',
        'mail.activity.mixin',
        'rating.mixin',
        'mail.tracking.duration.mixin',
        'html.field.history.mixin',
    ]
    _mail_post_access = 'read'
    _mail_thread_customer = True
    _order = "priority desc, sequence, date_deadline asc, id desc"
    _primary_email = 'email_from'
    _systray_view = 'list'
    _track_duration_field = 'stage_id'

    STATE_IN_PROGRESS = 'in_progress'
    STATE_DONE = 'done'
    STATE_CANCEL = 'cancel'
    STATE_CHOICES = [
        (STATE_IN_PROGRESS, 'En progreso'),
        (STATE_DONE, 'Terminada'),
        (STATE_CANCEL, 'Cancelada'),
    ]

    PRIORITY_CHOICES = [('0', 'Normal'), ('1', 'Alta')]

    project = fields.Many2one(
        'project.Project',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tasks',
        help_text='Proyecto (Odoo project_id).',
    )
    name = fields.Char(
        max_length=255,
        help_text='Título de la tarea (Odoo project.task.name).',
    )
    description = fields.Text(
        blank=True,
        default='',
        help_text='Descripción (Odoo description).',
    )
    priority = fields.Selection(
        max_length=1,
        choices=PRIORITY_CHOICES,
        default='0',
        help_text='Prioridad (Odoo priority).',
    )
    active = fields.Boolean(
        default=True,
        help_text='Tarea activa (Odoo active).',
    )
    sequence = fields.Integer(
        default=10,
        help_text='Orden (Odoo sequence).',
    )
    stage = fields.Many2one(
        'project.ProjectTaskType',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tasks',
        help_text='Etapa (Odoo stage_id).',
    )
    state = fields.Selection(
        max_length=16,
        choices=STATE_CHOICES,
        default=STATE_IN_PROGRESS,
        help_text='Estado (Odoo state).',
    )
    assignee = fields.Many2one(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='project_tasks',
        help_text='Responsable (Odoo user_ids).',
    )
    date_deadline = fields.Date(
        null=True,
        blank=True,
        help_text='Fecha límite (Odoo date_deadline).',
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
