"""
Models — addons.notifications (UC-NOT-06/07, en disolución hacia ``mail``).

Identifiers in English per DEC-DOC-005.

El buzón ``Notification`` (UC-NOT-01..05) + su ``NotificationType`` (slice 3a),
``NotificationPreference`` (UC-NOT-06, slice 3b) y ``ManualNotification``
(UC-NOT-07, slice 3c) se reubicaron a su hogar Odoo ``addons.mail`` (disolución
notifications→mail); se importan de allí. Aquí queda, hasta el slice 3d:

EmailTask — cola legacy (datos ya copiados a ``mail.mail``; retiro 3d pendiente).
"""
from django.db import models

from addons.base.models import TimeStampedModel


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
