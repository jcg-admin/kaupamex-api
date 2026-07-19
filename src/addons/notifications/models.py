"""
Models — addons.notifications (UC-NOT-06/07, en disolución hacia ``mail``).

Identifiers in English per DEC-DOC-005.

El buzón ``Notification`` (UC-NOT-01..05) + su ``NotificationType`` se reubicaron
a su hogar Odoo ``addons.mail`` (slice 3a de la disolución notifications→mail);
se importan de allí. Aquí quedan, hasta slices posteriores:

NotificationPreference — preferencias por tipo de notificacion (UC-NOT-06).
ManualNotification     — envios manuales del admin (UC-NOT-07).
EmailTask              — cola legacy (datos ya copiados a ``mail.mail``; retiro pendiente).
"""
from django.conf import settings
from django.db import models

from addons.base.models import TimeStampedModel
from addons.mail.models import NotificationType


class NotificationPreference(TimeStampedModel):
    """Preferencia user x type."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
    )
    type = models.CharField(
        max_length=32,
        choices=NotificationType.choices,
    )
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table             = 'notifications_preference'
        constraints          = [
            models.UniqueConstraint(
                fields=['user', 'type'],
                name='unique_notification_preference',
            )
        ]
        verbose_name         = 'Preferencia de notificacion'
        verbose_name_plural  = 'Preferencias de notificacion'

    def __str__(self):
        return f'{self.user_id}:{self.type}={self.enabled}'


class ManualNotification(TimeStampedModel):
    """Envio manual originado por staff. UC-NOT-07."""

    class RecipientType(models.TextChoices):
        USER = 'USER', 'Usuario especifico'
        PRODUCT_BUYERS = 'PRODUCT_BUYERS', 'Compradores de producto'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente'
        SENT = 'SENT', 'Enviado'
        FAILED = 'FAILED', 'Fallido'

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='manual_notifications_sent',
    )
    recipient_type = models.CharField(
        max_length=24, choices=RecipientType.choices,
    )
    recipient_identifier = models.CharField(max_length=150, blank=True, default='')
    product_id = models.PositiveIntegerField(null=True, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    recipients_count = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING,
    )

    class Meta:
        db_table = 'notifications_manual'
        ordering = ['-created_at']
        verbose_name = 'Notificacion manual'
        verbose_name_plural = 'Notificaciones manuales'

    def __str__(self):
        return f'Manual#{self.pk} {self.recipient_type} ({self.status})'


class EmailTask(TimeStampedModel):
    """
    Cola de emails pendientes para reintento automatico (Alt 2).

    Cada fila representa un envio que fallo en el thread pool (Alt 1).
    El management command send_pending_emails procesa filas PENDING y
    RETRYING con backoff exponencial (5 min × attempts).

    UC afectados: UC-NOT-01..05, UC-USR-02, UC-USR-04, UC-COM-01, UC-NEW-04.
    """

    class Status(models.TextChoices):
        PENDING  = 'pending',  'Pendiente'
        SENT     = 'sent',     'Enviado'
        FAILED   = 'failed',   'Fallido (max reintentos)'
        RETRYING = 'retrying', 'Reintentando'

    to           = models.TextField(help_text='Email destino. Multiples separados por coma.')
    subject      = models.CharField(max_length=255)
    body         = models.TextField()
    from_email   = models.CharField(max_length=254, blank=True, default='')
    scheduled_at = models.DateTimeField(auto_now_add=True)
    sent_at      = models.DateTimeField(null=True, blank=True)
    status       = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING,
    )
    attempts     = models.PositiveSmallIntegerField(default=0)
    last_error   = models.TextField(blank=True)
    max_attempts = models.PositiveSmallIntegerField(default=3)

    class Meta:
        db_table     = 'notifications_emailtask'
        ordering     = ['scheduled_at']
        verbose_name = 'Tarea de email'
        verbose_name_plural = 'Tareas de email'
        indexes = [
            models.Index(fields=['status', 'scheduled_at']),
        ]

    def __str__(self):
        return f'EmailTask#{self.pk} {self.status} → {self.to[:50]}'
