"""Modelo ``Project`` — addon ``project``.

Adaptación de Odoo ``project/models/project_project.py`` (``project.project``):
proyecto que agrupa tareas. Portado: ``name``/``description``/``active``/
``sequence``, cliente (``partner`` → AUTH_USER), ``company`` y ``unlink``.

pendiente: ``account_id`` (la cuenta analítica del proyecto,
``odoo19c: addons/project/models/project_project.py:98``) no está
declarado. ``account.analytic.account`` sí existe
(``addons/analytic/models/analytic_account.py``), así que la nota anterior
de esta cabecera —que la analítica no existía en este árbol— había
caducado; lo que falta es el campo. De él dependen dos pasos de ``unlink``.
"""

from django.conf import settings
import fields
import models

from addons.base.models import TimeStampedModel
from addons.web.models.res_users_settings_embedded_action import (
    ResUsersSettingsEmbeddedAction,
)


class Project(models.BaseModel, TimeStampedModel):
    """``project.project`` — proyecto que agrupa tareas."""

    #: Atributos de clase de ``project.project``, verbatim
    #: (``odoo19c: addons/project/models/project_project.py:24-36``).
    #: ``_inherit`` es aquí metadato: la herencia efectiva de los seis
    #: mixins queda fuera de este cambio
    #: (``designs/project-unlink-deletes-tasks.md``).
    _name = 'project.project'
    _description = "Project"
    _inherit = [
        'portal.mixin',
        'mail.alias.mixin',
        'rating.parent.mixin',
        'mail.activity.mixin',
        'mail.tracking.duration.mixin',
        'analytic.plan.fields.mixin',
    ]
    _order = "sequence, name, id"
    _rating_satisfaction_days = 30  # takes 30 days by default
    _track_duration_field = 'stage_id'

    name = fields.Char(
        max_length=200,
        help_text='Nombre del proyecto (Odoo project.project.name).',
    )
    description = fields.Text(
        blank=True,
        default='',
        help_text='Descripción (Odoo description).',
    )
    active = fields.Boolean(
        default=True,
        help_text='Proyecto activo (Odoo active).',
    )
    sequence = fields.Integer(
        default=10,
        help_text='Orden de presentación (Odoo sequence).',
    )
    partner = fields.Many2one(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='projects',
        help_text='Cliente (Odoo partner_id).',
    )
    company = fields.Many2one(
        'base.ResCompany',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='projects',
        help_text='Compañía (Odoo company_id).',
    )

    class Meta:
        db_table = 'project_project'
        ordering = ['sequence', 'name']
        verbose_name = 'Proyecto'
        verbose_name_plural = 'Proyectos'

    def __str__(self) -> str:
        return self.name

    def unlink(self):
        """≙ ``unlink`` (``odoo19c: addons/project/models/
        project_project.py:704-716``).

        La tarea guarda ``project_id`` como ``set null``: quien borra las
        tareas es este método, incluidas las archivadas.
        """
        # Delete the embedded action configs related to the deleted projects
        ResUsersSettingsEmbeddedAction.objects.filter(
            res_id__in=self.ids, res_model=self._name).delete()
        # pendiente: account_id — «Delete the empty related analytic
        # account» (``:709-713`` y ``:715``); el proyecto no declara el campo.
        self.with_context(active_test=False).env['project.task'].search(
            [('project', 'in', self.ids)]).unlink()
        return super().unlink()
