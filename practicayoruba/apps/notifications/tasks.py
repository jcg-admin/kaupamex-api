"""
Celery tasks — apps.notifications (D-004).

`dispatch_manual_fanout` se invoca desde
`AdminManualNotificationCreateView` cuando la audiencia supera el
umbral `MANUAL_FANOUT_ASYNC_THRESHOLD`. El cuerpo del task replica
exactamente el comportamiento sincrono que vivia inline en la view:
filtra preferencias y crea Notification por destinatario.

Comportamiento en tests:
- `CELERY_TASK_ALWAYS_EAGER=True` (override via @override_settings)
  hace que `.delay(...)` se ejecute inmediatamente en proceso, sin
  necesidad de un broker real (redis). Esto permite cubrir la rama
  async sin infraestructura.

Decision de diseno (DEC-DOC-005):
- Identificadores en ingles.
- El task NO crea el ManualNotification ni actualiza su `status`; la
  view ya lo persistio antes de despachar el fanout. El task solo
  crea Notification por destinatario.
"""
from celery import shared_task
from .models import Notification, NotificationPreference


@shared_task(name='notifications.dispatch_manual_fanout')
def dispatch_manual_fanout(user_ids, subject, message, notification_type):
    """Crea Notification para cada user_id respetando preferencias.

    Args:
        user_ids: lista de IDs de usuario destinatarios (ya resueltos
            por la view a partir de recipient_type/identifier/product_id).
        subject: asunto de la notificacion.
        message: cuerpo de la notificacion.
        notification_type: valor de NotificationType (p.ej. "PROMOTION").

    Returns:
        int: numero de Notification creadas (puede ser < len(user_ids)
        si algunos usuarios deshabilitaron este tipo en sus preferencias).
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
