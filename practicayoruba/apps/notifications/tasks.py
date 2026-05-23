"""
Fanout de notificaciones manuales — apps.notifications (UC-NOT-07).

dispatch_manual_fanout: crea Notification para cada user_id
respetando preferencias. Llamada directamente desde
AdminManualNotificationCreateView (sin broker — cnst-arquitectura T6).
"""
from .models import Notification, NotificationPreference


def dispatch_manual_fanout(user_ids, subject, message, notification_type):
    """Crea Notification para cada user_id respetando preferencias.

    Args:
        user_ids: lista de IDs de usuario destinatarios.
        subject: asunto de la notificacion.
        message: cuerpo de la notificacion.
        notification_type: valor de NotificationType.

    Returns:
        int: numero de Notification creadas.
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
    if to_create:
        Notification.objects.bulk_create(to_create)
    return len(to_create)
