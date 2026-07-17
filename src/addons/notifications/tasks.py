"""
Fanout de notificaciones manuales — addons.notifications (UC-NOT-07).

dispatch_manual_fanout: crea Notification para cada user_id
respetando preferencias. Llamada directamente desde
AdminManualNotificationCreateView (sin broker — cnst-arquitectura T6).
"""
import logging
from .models import Notification, NotificationPreference

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
