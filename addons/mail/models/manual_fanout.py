"""Fan-out de notificaciones manuales — servicio de la familia ``mail``.

Reubicado desde ``notifications.tasks`` (slice 3c de la disolucion
notifications->mail). ``dispatch_manual_fanout`` crea un item de buzon
``Notification`` por destinatario respetando su ``NotificationPreference``.
Es la contraparte de dispatch del wizard de composicion de Odoo (el envio a la
audiencia se materializa en los buzones de los seguidores).

Es un modulo de **servicio** (funcion de dominio), no un modelo: no se reexporta
en ``models/__init__`` — los consumidores importan la ruta completa
``addons.mail.models.manual_fanout`` (mismo criterio que ``email_executor``).
Llamado directamente por ``AdminManualNotificationCreateView`` (sin broker —
cnst-arquitectura T6).
"""
import logging

from .notification_inbox import Notification
from .notification_preference import NotificationPreference

logger = logging.getLogger('apps')


def dispatch_manual_fanout(user_ids, subject, message, notification_type):
    """Crea Notification para cada user_id respetando preferencias.

    Args:
        user_ids: lista de IDs de usuario destinatarios.
        subject: asunto de la notificacion.
        message: cuerpo de la notificacion.
        notification_type: valor de NotificationType.

    Returns:
        int: numero de Notification creadas (0 si falla silenciosamente).
    """
    if not user_ids:
        return 0

    disabled = set(
        NotificationPreference.objects
        .filter(
            user_id__in=user_ids,
            type=notification_type,
            enabled=False,
        )
        .values_list('user_id', flat=True)
    )
    to_create = [
        Notification(
            user_id=uid,
            type=notification_type,
            subject=subject,
            body=message,
        )
        for uid in user_ids
        if uid not in disabled
    ]
    if not to_create:
        return 0

    # H-CICLO21-06: bulk_create sin try/except propagaba excepciones de BD
    # al endpoint admin, causando HTTP 500. Se registra el error y se
    # retorna 0 para que el llamador pueda decidir cómo manejarlo.
    try:
        Notification.objects.bulk_create(to_create)
    except Exception:
        logger.exception(
            'dispatch_manual_fanout: bulk_create fallo para %d destinatarios '
            '(type=%s subject=%r)',
            len(to_create), notification_type, subject,
        )
        return 0

    return len(to_create)
