"""Preferencias de notificacion del comprador (familia ``mail``).

Reubicado desde el addon de proyecto ``notifications`` (en disolucion, slice 3b
de la familia ``mail``). En Odoo el opt-in/opt-out de notificaciones vive en el
backbone de mensajeria (``mail.notification`` + los ``notification_type`` del
seguidor); este ``NotificationPreference`` es la adaptacion de proyecto que
guarda, por usuario y por ``NotificationType``, si un canal esta habilitado.

Adaptacion de proyecto (no es un modelo Odoo 1:1): se conserva la tabla
``notifications_preference`` y su ``UniqueConstraint(user, type)`` intactos —
la reubicacion es state-only (mismo patron que el buzon ``Notification`` en el
slice 3a). Vive en ``mail`` porque la preferencia de notificacion es una
preocupacion del backbone de mensajeria; ``NotificationType`` es su hermano de
familia (``notification_inbox``).
"""
from django.conf import settings
from django.db import models

from addons.base.models import TimeStampedModel

from .notification_inbox import NotificationType


class NotificationPreference(TimeStampedModel):
    """Preferencia user x type (opt-in/opt-out por canal de notificacion)."""

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
        db_table = 'notifications_preference'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'type'],
                name='unique_notification_preference',
            )
        ]
        verbose_name = 'Preferencia de notificacion'
        verbose_name_plural = 'Preferencias de notificacion'

    def __str__(self):
        return f'{self.user_id}:{self.type}={self.enabled}'
