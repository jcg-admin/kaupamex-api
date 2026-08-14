"""Modelo ``Project`` — addon ``project``.

Adaptación de Odoo ``project/models/project_project.py`` (``project.project``):
proyecto que agrupa tareas. Núcleo portable: ``name``/``description``/``active``/
``sequence`` + cliente (``partner`` → AUTH_USER) y ``company`` (multi-company del
proyecto). Se omite la analítica contable de Odoo (``account.analytic.account``),
inexistente en este stack (Clausula 5).
"""
from django.conf import settings
import fields
import models

from addons.base.models import TimeStampedModel


class Project(TimeStampedModel):
    """``project.project`` — proyecto que agrupa tareas."""

    name        = fields.Char(
        max_length=200, help_text='Nombre del proyecto (Odoo project.project.name).',
    )
    description = fields.Text(
        blank=True, default='', help_text='Descripción (Odoo description).',
    )
    active      = fields.Boolean(
        default=True, help_text='Proyecto activo (Odoo active).',
    )
    sequence    = fields.Integer(
        default=10, help_text='Orden de presentación (Odoo sequence).',
    )
    partner     = fields.Many2one(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='projects', help_text='Cliente (Odoo partner_id).',
    )
    company     = fields.Many2one(
        'base.ResCompany', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='projects', help_text='Compañía (Odoo company_id).',
    )

    class Meta:
        db_table = 'project_project'
        ordering = ['sequence', 'name']
        verbose_name = 'Proyecto'
        verbose_name_plural = 'Proyectos'

    def __str__(self) -> str:
        return self.name
