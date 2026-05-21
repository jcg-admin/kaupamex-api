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
from .emails import (
    send_order_confirmation_email,
    send_order_status_email,
    send_shipping_update_email,
    send_return_processed_email,
    send_refund_email,
)


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


@shared_task(name='notifications.send_order_confirmation_email')
def send_order_confirmation_email_task(user_email, user_name, order_number, order_total):
    """UC-NOT-01: email de confirmacion de orden (async via Celery)."""
    send_order_confirmation_email(user_email, user_name, order_number, order_total)


@shared_task(name='notifications.send_order_status_email')
def send_order_status_email_task(user_email, user_name, order_number, new_status, tracking_number=None):
    """UC-NOT-02: email de cambio de estado de orden (async via Celery)."""
    send_order_status_email(user_email, user_name, order_number, new_status, tracking_number)


@shared_task(name='notifications.send_shipping_update_email')
def send_shipping_update_email_task(user_email, user_name, order_number, tracking_number=None, event_description=None):
    """UC-NOT-03: email de actualizacion de envio (async via Celery)."""
    send_shipping_update_email(user_email, user_name, order_number, tracking_number, event_description)


@shared_task(name='notifications.send_return_processed_email')
def send_return_processed_email_task(user_email, user_name, order_number, return_status, reason=None):
    """UC-NOT-04: email de devolucion procesada (async via Celery)."""
    send_return_processed_email(user_email, user_name, order_number, return_status, reason)


@shared_task(name='notifications.send_refund_email')
def send_refund_email_task(user_email, user_name, order_number, amount_refunded):
    """UC-NOT-05: email de reembolso procesado (async via Celery)."""
    send_refund_email(user_email, user_name, order_number, amount_refunded)
