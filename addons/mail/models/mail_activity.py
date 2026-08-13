"""``mail.activity`` — actividad planificada sobre un registro (Odoo ``mail``).

Portacion fiel de ``MailActivity``
(``scratchpad/odoo19x/addons/mail/models/mail_activity.py:50-97``, Odoo 19;
identico en campos a 18) — un "to-do" con plazo asignado a un usuario sobre
cualquier documento (par polimorfico ``res_model``+``res_id``), que en Odoo
heredan los modelos via ``mail.thread`` (``activity_schedule``). Parte de la
familia ``mail`` (SOL-096).

Fuente Odoo community (LGPL-3): copia + adaptacion con atribucion.

- ``user`` ← ``user_id`` (Odoo ``res.users``, asignado): party = ``IdentityUser``.
- ``state`` (Odoo ``:92`` computed ``overdue/today/planned/done``): aqui es una
  ``@property`` derivada de ``date_deadline``. **La referencia tampoco lo
  almacena** — ``compute='_compute_state'`` sin ``store=True``
  (``odoo19c: mail/models/mail_activity.py:92-97``), asi que la ``property``
  es fiel y no hay mecanismo ausente que la justifique. El estado ``done`` en Odoo
  se materializa al completar (``action_done`` publica un mensaje y elimina la
  actividad) — se replica en ``action_done`` abajo.
"""
from django.conf import settings
from django.utils import timezone

import fields
import models
from addons.base.models import TimeStampedModel

from .mail_message import MailMessage


class MailActivity(TimeStampedModel):
    """``mail.activity`` — actividad planificada sobre un registro polimorfico."""

    STATE_OVERDUE = 'overdue'
    STATE_TODAY = 'today'
    STATE_PLANNED = 'planned'

    res_model = fields.Char(
        max_length=128,
        help_text='Modelo del registro, p. ej. "support.SupportTicket" (Odoo res_model).',
    )
    res_id = fields.Integer(
        null=True, blank=True,
        help_text='ID del registro (Odoo res_id, Integer plano).',
    )
    activity_type = fields.Many2one(
        'mail.MailActivityType', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='activities',
        help_text='Tipo de actividad (Odoo activity_type_id).',
    )
    summary = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Resumen (Odoo summary).',
    )
    note = fields.Html(
        blank=True, default='',
        help_text='Nota (Odoo note).',
    )
    date_deadline = fields.Date(
        null=False, blank=True, default=timezone.localdate,
        help_text='Fecha limite (Odoo date_deadline, default hoy).',
    )
    user = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='assigned_activities',
        help_text='Usuario asignado (Odoo user_id → res.users; party = IdentityUser).',
    )
    automated = fields.Boolean(
        default=False,
        help_text='Generada por una regla automatica, no manual (Odoo automated).',
    )

    class Meta:
        db_table = 'mail_activity'
        ordering = ['date_deadline', 'id']
        verbose_name = 'Actividad'
        verbose_name_plural = 'Actividades'
        indexes = [
            models.Index(fields=['res_model', 'res_id'], name='mail_activity_record_idx'),
            models.Index(fields=['user', 'date_deadline'], name='mail_activity_user_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.summary or (self.activity_type_id and "actividad")} @ {self.date_deadline}'

    @property
    def state(self) -> str:
        """Estado derivado del plazo (Odoo ``state`` computed: overdue/today/planned)."""
        today = timezone.localdate()
        if self.date_deadline < today:
            return self.STATE_OVERDUE
        if self.date_deadline == today:
            return self.STATE_TODAY
        return self.STATE_PLANNED

    def action_done(self, feedback=''):
        """Completa la actividad: publica un mensaje en el hilo y la elimina.

        Fiel al comportamiento de ``mail.activity._action_done`` de Odoo (publica
        un ``mail.message`` de tipo ``notification`` en el documento y desvincula
        la actividad). Devuelve el ``MailMessage`` publicado.
        """
        body = f'{self.summary or ""}'.strip()
        if feedback:
            body = f'{body}: {feedback}' if body else feedback
        message = MailMessage.objects.create(
            model=self.res_model, res_id=self.res_id,
            body=body or 'Actividad completada',
            message_type=MailMessage.TYPE_NOTIFICATION,
            author=self.user,
        )
        self.delete()
        return message
