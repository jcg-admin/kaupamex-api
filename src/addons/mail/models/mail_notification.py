"""``mail.notification`` — registro de entrega por destinatario (Odoo ``mail``).

Portacion fiel de ``mail/models/mail_notification.py`` (``mail.notification``,
Odoo 19 community, LGPL-3). Es la fila que ata un ``mail.message`` a UN
destinatario con su **estado de entrega** y de **lectura**, y su tipo de canal
(inbox / email / sms). En Odoo es la tabla que permite el buzon "Inbox", los
acuses de lectura y el seguimiento de rebotes/errores de correo por
destinatario.

Relacion en el backbone: cuando ``MailThread.message_post`` publica un mensaje,
se materializa una ``MailNotification`` de tipo ``inbox`` por cada **seguidor**
del registro (menos el autor) — igual que el ``_notify_thread`` de Odoo reparte
el mensaje a los followers. Los canales ``email`` / ``sms`` cuelgan del mismo
registro con un cross-link al envio saliente concreto (``mail.mail`` = la cola
``MailMail``, hogar Odoo fiel de la ex-``EmailTask``; ``SmsSms`` de ``sms`` ≙
``sms.sms``), referenciados por **string** para no acoplar el orden de import
(Django resuelve la FK de forma diferida).
"""
from django.conf import settings
from django.utils import timezone

import fields
import models

from addons.base.models import TimeStampedModel

from .mail_message import MailMessage


class MailNotification(TimeStampedModel):
    """``mail.notification`` — entrega de un ``mail.message`` a un destinatario."""

    # Odoo notification_type (mail_notification.py) — canal de entrega. Se
    # portan inbox/email/sms; ``snail`` (snailmail) queda fuera (no hay correo
    # postal en este stack).
    TYPE_INBOX = 'inbox'
    TYPE_EMAIL = 'email'
    TYPE_SMS = 'sms'
    NOTIFICATION_TYPE_CHOICES = [
        (TYPE_INBOX, 'Inbox'),
        (TYPE_EMAIL, 'Email'),
        (TYPE_SMS, 'SMS'),
    ]

    # Odoo notification_status — ciclo de vida de la entrega.
    STATUS_READY = 'ready'
    STATUS_PROCESS = 'process'
    STATUS_SENT = 'sent'
    STATUS_BOUNCE = 'bounce'
    STATUS_EXCEPTION = 'exception'
    STATUS_CANCELED = 'canceled'
    NOTIFICATION_STATUS_CHOICES = [
        (STATUS_READY, 'Ready to Send'),
        (STATUS_PROCESS, 'Processing'),
        (STATUS_SENT, 'Sent'),
        (STATUS_BOUNCE, 'Bounced'),
        (STATUS_EXCEPTION, 'Exception'),
        (STATUS_CANCELED, 'Canceled'),
    ]

    # Odoo failure_type — clasificacion del fallo de entrega (texto acotado).
    FAILURE_UNKNOWN = 'unknown'
    FAILURE_MAIL_EMAIL_INVALID = 'mail_email_invalid'
    FAILURE_MAIL_SMTP = 'mail_smtp'
    FAILURE_SMS_NUMBER_MISSING = 'sms_number_missing'
    FAILURE_SMS_CREDIT = 'sms_credit'
    FAILURE_TYPE_CHOICES = [
        (FAILURE_UNKNOWN, 'Unknown error'),
        (FAILURE_MAIL_EMAIL_INVALID, 'Invalid email address'),
        (FAILURE_MAIL_SMTP, 'Connection failed (SMTP)'),
        (FAILURE_SMS_NUMBER_MISSING, 'Missing number'),
        (FAILURE_SMS_CREDIT, 'Insufficient credit'),
    ]

    # Odoo mail_message_id (required, ondelete cascade).
    message = fields.Many2one(
        MailMessage, on_delete=models.CASCADE,
        related_name='notification_ids',
        help_text='Mensaje entregado (Odoo mail_message_id).',
    )
    # Odoo res_partner_id (recipient, ondelete cascade). En este stack el
    # destinatario es el usuario/party (AUTH_USER_MODEL), no res.partner.
    partner = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='mail_notifications',
        help_text='Destinatario (Odoo res_partner_id).',
    )
    notification_type = fields.Selection(
        max_length=8, choices=NOTIFICATION_TYPE_CHOICES, default=TYPE_INBOX,
        help_text='Canal de entrega (Odoo notification_type).',
    )
    notification_status = fields.Selection(
        max_length=12, choices=NOTIFICATION_STATUS_CHOICES, default=STATUS_READY,
        help_text='Estado de entrega (Odoo notification_status).',
    )
    is_read = fields.Boolean(
        default=False, help_text='Leido por el destinatario (Odoo is_read).',
    )
    read_date = fields.Datetime(
        null=True, blank=True,
        help_text='Momento de lectura (Odoo read_date).',
    )
    failure_type = fields.Selection(
        max_length=32, choices=FAILURE_TYPE_CHOICES, null=True, blank=True,
        help_text='Clasificacion del fallo (Odoo failure_type).',
    )
    failure_reason = fields.Text(
        blank=True, default='',
        help_text='Detalle del fallo (Odoo failure_reason).',
    )
    # Cross-link al envio saliente concreto (Odoo ``mail_mail_id``). Ahora apunta
    # al hogar fiel ``mail.mail`` (``MailMail``), ex-``notifications.EmailTask``.
    # String FK para no acoplar el orden de import; SET_NULL: el registro de
    # entrega sobrevive al purgado de la cola de envio.
    mail_mail = fields.Many2one(
        'mail.MailMail', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='mail_notifications',
        help_text='Envio de correo asociado (Odoo mail_mail_id).',
    )
    sms = fields.Many2one(
        'sms.SmsSms', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='mail_notifications',
        help_text='SMS saliente asociado (Odoo sms_id).',
    )

    class Meta:
        db_table = 'mail_notification'
        ordering = ['-created_at', '-id']
        verbose_name = 'Notificacion de mensaje'
        verbose_name_plural = 'Notificaciones de mensaje'
        indexes = [
            models.Index(fields=['partner', 'is_read']),
            models.Index(fields=['notification_type', 'notification_status']),
        ]

    def __str__(self) -> str:
        return (
            f'MailNotification#{self.pk} msg={self.message_id} '
            f'→ {self.partner_id} [{self.notification_type}/{self.notification_status}]'
        )

    def mark_read(self) -> None:
        """Marca la notificacion como leida (Odoo ``is_read=True``, ``read_date``)."""
        self.is_read = True
        self.read_date = timezone.now()
        self.notification_status = self.STATUS_SENT
        self.save(update_fields=[
            'is_read', 'read_date', 'notification_status', 'updated_at',
        ])
