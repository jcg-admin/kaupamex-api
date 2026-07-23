"""``mailing.trace`` — rastreo de entrega por destinatario (Odoo ``mass_mailing``).

Portacion fiel de ``mass_mailing/models/mailing_trace.py`` (``mailing.trace``,
Odoo 19 community, LGPL-3): una fila por (campana, destinatario) con el estado
de entrega y los timestamps de envio/apertura/respuesta. Es el analogo
mass-mailing de ``mail.notification`` — pero el destinatario de un envio masivo
es un ``mailing.contact`` (posiblemente anonimo), no un usuario/partner, por eso
el rastreo vive aqui y no en el backbone ``mail``.

Nota: este modelo se habia portado por error dentro del addon de proyecto
``newsletter`` (revertido, 2026-07-19); su hogar Odoo fiel es ``mass_mailing``.
"""
import fields
import models

from addons.base.models import TimeStampedModel

from .mailing_contact import MailingContact
from .mailing_mailing import MailingMailing


class MailingTrace(TimeStampedModel):
    """``mailing.trace`` — entrega de un envio masivo a un destinatario."""

    # Odoo trace_status (mailing_trace.py:87).
    STATUS_OUTGOING = 'outgoing'
    STATUS_PROCESS = 'process'
    STATUS_PENDING = 'pending'
    STATUS_SENT = 'sent'
    STATUS_OPEN = 'open'
    STATUS_REPLY = 'reply'
    STATUS_BOUNCE = 'bounce'
    STATUS_ERROR = 'error'
    STATUS_CANCEL = 'cancel'
    STATUS_CHOICES = [
        (STATUS_OUTGOING, 'En cola'),
        (STATUS_PROCESS, 'Procesando'),
        (STATUS_PENDING, 'Enviado'),
        (STATUS_SENT, 'Entregado'),
        (STATUS_OPEN, 'Abierto'),
        (STATUS_REPLY, 'Respondido'),
        (STATUS_BOUNCE, 'Rebotado'),
        (STATUS_ERROR, 'Excepcion'),
        (STATUS_CANCEL, 'Cancelado'),
    ]

    # Odoo failure_type (mailing_trace.py:97) — subset portado.
    FAILURE_UNKNOWN = 'unknown'
    FAILURE_MAIL_BOUNCE = 'mail_bounce'
    FAILURE_MAIL_EMAIL_INVALID = 'mail_email_invalid'
    FAILURE_MAIL_EMAIL_MISSING = 'mail_email_missing'
    FAILURE_MAIL_SMTP = 'mail_smtp'
    FAILURE_MAIL_OPTOUT = 'mail_optout'
    FAILURE_CHOICES = [
        (FAILURE_UNKNOWN, 'Error desconocido'),
        (FAILURE_MAIL_BOUNCE, 'Rebote'),
        (FAILURE_MAIL_EMAIL_INVALID, 'Email invalido'),
        (FAILURE_MAIL_EMAIL_MISSING, 'Email ausente'),
        (FAILURE_MAIL_SMTP, 'Fallo de conexion (SMTP)'),
        (FAILURE_MAIL_OPTOUT, 'Dado de baja'),
    ]

    mailing = fields.Many2one(
        MailingMailing, on_delete=models.CASCADE, related_name='trace_ids',
        help_text='Envio masivo rastreado (Odoo mass_mailing_id).',
    )
    contact = fields.Many2one(
        MailingContact, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='trace_ids', help_text='Destinatario (Odoo res_id).',
    )
    # Snapshot del email al momento del envio (Odoo email). Sobrevive al borrado
    # del contacto para conservar el historial de entrega.
    email = fields.Char(max_length=254, blank=True, default='')
    trace_status = fields.Selection(
        max_length=12, choices=STATUS_CHOICES, default=STATUS_OUTGOING,
        help_text='Estado de entrega (Odoo trace_status).',
    )
    sent_datetime = fields.Datetime(null=True, blank=True)
    open_datetime = fields.Datetime(null=True, blank=True)
    reply_datetime = fields.Datetime(null=True, blank=True)
    failure_type = fields.Selection(
        max_length=24, choices=FAILURE_CHOICES, null=True, blank=True,
    )
    failure_reason = fields.Text(blank=True, default='')

    class Meta:
        db_table = 'mailing_trace'
        ordering = ['-created_at', '-id']
        verbose_name = 'Traza de envio masivo'
        verbose_name_plural = 'Trazas de envio masivo'
        constraints = [
            models.UniqueConstraint(
                fields=['mailing', 'contact'],
                name='unique_mailing_trace',
            ),
        ]
        indexes = [
            models.Index(fields=['mailing', 'trace_status']),
        ]

    def __str__(self) -> str:
        return (
            f'Trace#{self.pk} mailing={self.mailing_id} '
            f'{self.email} [{self.trace_status}]'
        )
