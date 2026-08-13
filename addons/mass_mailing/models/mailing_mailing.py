"""``mailing.mailing`` — un envio masivo / campana (Odoo ``mass_mailing``).

Portacion fiel de ``mass_mailing/models/mailing.py`` (``mailing.mailing``, Odoo
19 community, LGPL-3): la campana de correo masivo. En Odoo ``_inherit`` incluye
``mail.thread`` (chatter) — aqui se hereda el mixin ``MailThread`` del addon
``mail``, así la campana gana historial de mensajes/seguidores como cualquier
documento. Es el hogar del ``NewsletterCampaign`` de proyecto (disuelto).

Alcance portado: nucleo de contenido + audiencia + estado. El scheduling por
cron, A/B testing, UTM (``utm.campaign``/``medium``/``source``) y adjuntos de
Odoo quedan fuera de este paso (Clausula 5 — se portan al haber flujo real).
"""
from django.conf import settings

import fields
import models

from addons.base.models import TimeStampedModel
from addons.mail.models import MailThread

from .mailing_list import MailingList


class MailingMailing(MailThread, TimeStampedModel):
    """``mailing.mailing`` — campana de correo masivo (hereda ``mail.thread``)."""

    # Odoo state (mailing.py:129) — colapsado a los estados que este stack usa.
    STATE_DRAFT = 'draft'
    STATE_IN_QUEUE = 'in_queue'
    STATE_SENDING = 'sending'
    STATE_DONE = 'done'
    STATE_CHOICES = [
        (STATE_DRAFT, 'Borrador'),
        (STATE_IN_QUEUE, 'En cola'),
        (STATE_SENDING, 'Enviando'),
        (STATE_DONE, 'Enviado'),
    ]

    subject = fields.Char(
        max_length=255, help_text='Asunto del correo (Odoo subject).',
    )
    preview = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Texto de vista previa (Odoo preview).',
    )
    email_from = fields.Char(
        max_length=254, blank=True, default='',
        help_text='Remitente (Odoo email_from).',
    )
    body_html = fields.Html(
        blank=True, default='', help_text='Cuerpo HTML (Odoo body_html).',
    )
    state = fields.Selection(
        max_length=12, choices=STATE_CHOICES, default=STATE_DRAFT,
        help_text='Estado del envio (Odoo state).',
    )
    sent_date = fields.Datetime(
        null=True, blank=True, help_text='Fecha de envio (Odoo sent_date).',
    )
    schedule_date = fields.Datetime(
        null=True, blank=True,
        help_text='Envio programado (Odoo schedule_date).',
    )
    user = fields.Many2one(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='mailings_sent', help_text='Responsable (Odoo user_id).',
    )
    contact_lists = fields.Many2many(
        MailingList, blank=True, related_name='mailing_ids',
        help_text='Listas destinatarias (Odoo contact_list_ids).',
    )

    class Meta:
        db_table = 'mailing_mailing'
        ordering = ['-created_at', '-id']
        verbose_name = 'Envio masivo'
        verbose_name_plural = 'Envios masivos'

    def __str__(self) -> str:
        return self.subject or f'Mailing#{self.pk}'
