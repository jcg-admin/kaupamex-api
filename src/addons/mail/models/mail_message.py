"""``mail.message`` — mensaje del chatter (Odoo ``mail``).

Portacion fiel de ``Message``
(``scratchpad/odoo19x/addons/mail/models/mail_message.py:88-191``, Odoo 19;
identico en campos a 18) — el registro de un mensaje adjunto a cualquier
documento de negocio de forma polimorfica (``model``+``res_id`` como campos
planos, igual que ``ir.attachment``; Odoo tampoco usa una FK real ahi). Es el
backbone del historial de conversacion/actividad ("chatter") que en Odoo
heredan casi todos los modelos de negocio via ``mail.thread``. Parte de la
familia ``mail`` (SOL-096).

Fuente Odoo community (LGPL-3): copia + adaptacion con atribucion.

Mapeo de campos PROVEN contra la fuente (``mail_message.py`` Odoo 19):

- ``model`` (``:113``, Char "Related Document Model") — aqui almacena el label
  Django del modelo, p. ej. ``"support.SupportTicket"`` (lo escribe
  ``mail.thread._mail_thread_res_model``).
- ``res_id`` (``:114``, ``Many2oneReference`` → aqui ``Integer`` plano, mismo
  criterio que ``ir.attachment.res_id``: el ORM shim no tiene un tipo
  ``Many2oneReference`` fiel y Odoo tampoco lo trata como FK real).
- ``author`` ← ``author_id`` (``:145``, Odoo ``res.partner``): en este proyecto
  el party es ``users.IdentityUser`` (DEC-SALE-01), asi que la FK apunta a
  ``AUTH_USER_MODEL``.
- ``subtype`` ← ``subtype_id`` (``:138``, FK ``mail.message.subtype``,
  ``ondelete='set null'``).
- ``message_type`` (``:119-125``): selection fiel de 5 valores.

NO se porta en este slice (la mecanica ``@api`` de Odoo se adapta al framework,
o pertenece a otra capa): el motor de envio de correo saliente (``mail.mail``,
ya cubierto por ``email_executor``), los ``tracking_value_ids`` (auditoria de
cambios de campo — micro-paso siguiente de la familia), los ``attachment_ids``
(se resuelven con ``ir.attachment`` ya portado, wiring posterior), y las ACL de
lectura de Odoo (aqui es DRF ``HasCapability``, DEC-11).
"""
from django.conf import settings
from django.utils import timezone

import fields
import models
from addons.base.models import TimeStampedModel


class MailMessage(TimeStampedModel):
    """``mail.message`` — un mensaje del chatter vinculado a un registro."""

    TYPE_EMAIL = 'email'
    TYPE_COMMENT = 'comment'
    TYPE_EMAIL_OUTGOING = 'email_outgoing'
    TYPE_NOTIFICATION = 'notification'
    TYPE_AUTO_COMMENT = 'auto_comment'
    MESSAGE_TYPE_CHOICES = [
        (TYPE_EMAIL, 'Incoming Email'),
        (TYPE_COMMENT, 'Comment'),
        (TYPE_EMAIL_OUTGOING, 'Outgoing Email'),
        (TYPE_NOTIFICATION, 'System notification'),
        (TYPE_AUTO_COMMENT, 'Automated Targeted Notification'),
    ]

    subject = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Asunto del mensaje (Odoo subject).',
    )
    date = fields.Datetime(
        default=None, null=True, blank=True,
        help_text='Fecha del mensaje (Odoo date, default now — se fija en save()).',
    )
    body = fields.Html(
        blank=True, default='',
        help_text='Contenido HTML del mensaje (Odoo body; saneo en capa UI).',
    )
    model = fields.Char(
        max_length=128, blank=True, default='',
        help_text=(
            'Modelo polimorfico referenciado, p. ej. "support.SupportTicket" '
            '(Odoo model). NO es una FK — vinculo plano igual que Odoo.'
        ),
    )
    res_id = fields.Integer(
        null=True, blank=True,
        help_text='ID del registro referenciado (Odoo res_id, Integer plano).',
    )
    parent = fields.Many2one(
        'mail.MailMessage', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='children',
        help_text='Mensaje padre para el hilo de conversacion (Odoo parent_id).',
    )
    record_name = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Nombre legible del registro referenciado (Odoo record_name).',
    )
    message_type = fields.Selection(
        max_length=16, choices=MESSAGE_TYPE_CHOICES, default=TYPE_COMMENT,
        help_text='Tipo de mensaje (Odoo message_type).',
    )
    subtype = fields.Many2one(
        'mail.MailMessageSubtype', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='messages',
        help_text='Subtipo del mensaje (Odoo subtype_id).',
    )
    author = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='authored_messages',
        help_text='Autor del mensaje (Odoo author_id → res.partner; party = IdentityUser).',
    )
    email_from = fields.Char(
        max_length=254, blank=True, default='',
        help_text='Remitente cuando no hay autor registrado (Odoo email_from).',
    )
    reply_to = fields.Char(
        max_length=254, blank=True, default='',
        help_text='Direccion Reply-To (Odoo reply_to).',
    )

    class Meta:
        db_table = 'mail_message'
        ordering = ['-id']
        verbose_name = 'Mensaje'
        verbose_name_plural = 'Mensajes'
        indexes = [
            models.Index(fields=['model', 'res_id'], name='mail_message_record_idx'),
            models.Index(fields=['author'], name='mail_message_author_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.model}#{self.res_id} — {self.subject or self.message_type}'

    def save(self, *args, **kwargs):
        """Fija ``date`` a la fecha de creacion si no se dio — equivalente del
        ``default=fields.Datetime.now`` de Odoo (``mail_message.py:92``). No se
        usa ``auto_now_add`` porque ``date`` es reasignable (reenvio/import)."""
        if self.date is None:
            self.date = timezone.now()
        super().save(*args, **kwargs)
