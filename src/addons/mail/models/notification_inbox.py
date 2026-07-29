"""Buzón de notificaciones del comprador — read-model del inbox (familia ``mail``).

Reubicado desde el addon de proyecto ``notifications`` (en disolución, slice 3a
de la familia ``mail``). En Odoo el "Inbox" NO es una tabla propia: se materializa
de ``mail.message`` + ``mail.notification`` (``notification_type='inbox'``) por
seguidor. Este ``Notification`` es el **read-model denormalizado** que el
comprador ve (asunto/cuerpo/leído por evento de negocio), puenteado al backbone
por ``mail_message`` (FK a ``mail.MailMessage``) + ``from_mail_message``.

Adaptación de proyecto (no es un modelo Odoo 1:1): se conserva la tabla
``notifications_notification`` y el contrato de API ``/api/v2/notifications/``
intactos — la reubicación es state-only (mismo patrón que newsletter→mass_mailing).
Vive en ``mail`` porque el inbox es una preocupación del backbone de mensajería.
Los envíos salientes (``mail.mail``) y la entrega por destinatario
(``mail.notification``) son modelos hermanos de esta misma familia.
"""
from django.conf import settings
from django.db import models

from addons.base.models import TimeStampedModel
from addons.bus.mixins import BusListenerMixin
from addons.bus.services import user_channel


class NotificationType(models.TextChoices):
    """Tipos soportados de notificaciones (English, DEC-DOC-005)."""

    ORDER_UPDATE = 'ORDER_UPDATE', 'Actualizacion de orden'
    RETURN_UPDATE = 'RETURN_UPDATE', 'Actualizacion de devolucion'
    PROMOTION = 'PROMOTION', 'Promocion'
    SYSTEM = 'SYSTEM', 'Sistema'
    SUPPORT_UPDATE = 'SUPPORT_UPDATE', 'Actualizacion de soporte'


# Tipos obligatorios — el usuario no puede deshabilitarlos.
MANDATORY_NOTIFICATION_TYPES = frozenset({
    NotificationType.ORDER_UPDATE,
    NotificationType.RETURN_UPDATE,
    NotificationType.SYSTEM,
})


# Etiquetas user-facing por tipo.
NOTIFICATION_TYPE_LABELS = {
    NotificationType.ORDER_UPDATE: 'Actualizaciones de orden',
    NotificationType.RETURN_UPDATE: 'Actualizaciones de devolucion',
    NotificationType.PROMOTION: 'Promociones',
    NotificationType.SYSTEM: 'Mensajes del sistema',
    NotificationType.SUPPORT_UPDATE: 'Actualizaciones de soporte',
}


class Notification(BusListenerMixin, TimeStampedModel):
    """Notificacion individual en el buzon de un usuario (read-model del inbox).

    Emite al bus al crearse (T-079). El emisor va en el modelo y no en cada
    ``notify_*`` del servicio porque la creación **es** el evento: así todo
    productor —presente y futuro— queda cubierto por construcción, sin depender
    de que alguien recuerde emitir.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    type = models.CharField(
        max_length=32,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM,
    )
    subject = models.CharField(max_length=200)
    body = models.TextField()
    read = models.BooleanField(default=False)
    # Puente al backbone de chatter (familia mail): si esta notificacion se
    # origino en un mensaje del hilo de un registro (``MailThread.message_post``),
    # apunta al ``mail.message`` fuente. NULL para las notificaciones que no
    # nacen del chatter (la mayoria de las transaccionales del servicio). Es la
    # contraparte de ``mail.notification`` inbox: aquel rastrea la ENTREGA por
    # destinatario; este es el item de BUZON que ve el comprador. SET_NULL: el
    # buzon sobrevive al purgado del mensaje.
    mail_message = models.ForeignKey(
        'mail.MailMessage',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='inbox_notifications',
        help_text='Mensaje de chatter que origino esta notificacion (familia mail).',
    )

    class Meta:
        db_table = 'notifications_notification'
        ordering = ['-created_at']
        verbose_name = 'Notificacion'
        verbose_name_plural = 'Notificaciones'
        indexes = [
            models.Index(fields=['user', 'read'], name='notificatio_user_id_878a13_idx'),
            models.Index(fields=['user', '-created_at'], name='notificatio_user_id_05b4bc_idx'),
        ]

    def __str__(self):
        return f'#{self.pk} {self.subject} ({self.type})'

    def bus_channel_key(self) -> str:
        return user_channel(self.user)

    def save(self, *args, **kwargs):
        es_nueva = self._state.adding
        super().save(*args, **kwargs)
        if es_nueva:
            # Sólo la creación es noticia. Marcar leída actualiza la fila y no
            # debe reemitir: el cliente ya sabe de esta notificación.
            self._bus_send('notificacion', {
                'id': self.pk,
                'type': self.type,
                'subject': self.subject,
            })

    @classmethod
    def from_mail_message(cls, message, user, type=None):
        """Materializa un item de buzon a partir de un ``mail.message`` del hilo.

        Puente fiel del backbone: cualquier registro que herede ``MailThread``
        puede aflorar un mensaje de su chatter al buzon del comprador. Copia
        ``subject``/``body`` del mensaje y guarda el enlace ``mail_message``.
        Devuelve la ``Notification`` creada.
        """
        return cls.objects.create(
            user=user,
            type=type or NotificationType.SYSTEM,
            subject=(message.subject or '')[:200],
            body=message.body or '',
            mail_message=message,
        )
