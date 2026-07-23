"""Notificacion manual del admin — envio dirigido a una audiencia (familia ``mail``).

Reubicado desde el addon de proyecto ``notifications`` (en disolucion, slice 3c
de la familia ``mail``). En Odoo un envio manual del staff a una audiencia se
compone con el wizard ``mail.compose.message`` / ``mail.mass_mailing``; este
``ManualNotification`` es la adaptacion de proyecto que registra el broadcast
(quien lo envio, a que audiencia, con que resultado). El fan-out real a los
buzones ``Notification`` (respetando ``NotificationPreference``) lo hace el
servicio hermano ``manual_fanout.dispatch_manual_fanout``.

Adaptacion de proyecto (no es un modelo Odoo 1:1): se conserva la tabla
``notifications_manual`` intacta — la reubicacion es state-only (mismo patron
que el buzon en 3a y la preferencia en 3b). Vive en ``mail`` porque el envio
manual a una audiencia es una preocupacion del backbone de mensajeria.
"""
from django.conf import settings
from django.db import models

from addons.base.models import TimeStampedModel


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
