"""
service.py — apps.notifications
Servicios de notificacion transaccional. UC-NOT-01..05.

Cada funcion `notify_*` hace dos cosas:
1. Crea la Notification in-app (debe llamarse dentro de transaction.atomic).
2. Despacha el email via Celery con on_commit (garantiza despacho solo si
   la transaccion commitea).

La separacion es intencional: in-app dentro de la transaccion mantiene
consistencia; email fuera evita enviar si el checkout/transicion falla.
"""
from django.db import transaction
from .models import Notification, NotificationType
from .tasks import (
    send_order_confirmation_email_task,
    send_order_status_email_task,
    send_shipping_update_email_task,
    send_return_processed_email_task,
    send_refund_email_task,
)


def notify_order_created(order, user, total_amount):
    """
    UC-NOT-01: notificacion de confirmacion de orden.
    Llamar dentro de transaction.atomic() post-creacion de la Order.
    """
    if not user or not getattr(user, 'pk', None):
        return

    Notification.objects.create(
        user=user,
        type=NotificationType.ORDER_UPDATE,
        subject=f'Orden confirmada #{order.order_number}',
        body=(
            f'Tu orden #{order.order_number} ha sido recibida y '
            f'esta siendo procesada. Total: ${total_amount}.'
        ),
    )

    if user.email:
        user_email  = user.email
        name        = user.first_name or user.username
        order_num   = order.order_number
        total_str   = str(total_amount)
        transaction.on_commit(
            lambda: send_order_confirmation_email_task.delay(
                user_email, name, order_num, total_str,
            )
        )


def notify_order_status_changed(order, new_status):
    """
    UC-NOT-02: notificacion de cambio de estado de orden.
    Llamar dentro de transaction.atomic() post-transicion de estado.
    Solo notifica estados relevantes (FR-NOT-02.02).
    """
    notify_statuses = {
        'PAYMENT_CONFIRMED', 'IN_PREPARATION', 'SHIPPED',
        'DELIVERED', 'CANCELLED', 'CANCELLED_TIMEOUT',
    }
    if new_status not in notify_statuses:
        return

    user = getattr(order, 'user', None)
    if not user or not getattr(user, 'pk', None):
        return

    _labels = {
        'PAYMENT_CONFIRMED': 'Pago confirmado',
        'IN_PREPARATION':    'Pedido en preparacion',
        'SHIPPED':           'Pedido enviado',
        'DELIVERED':         'Pedido entregado',
        'CANCELLED':         'Orden cancelada',
        'CANCELLED_TIMEOUT': 'Orden cancelada por tiempo agotado',
    }
    label = _labels.get(new_status, new_status)

    Notification.objects.create(
        user=user,
        type=NotificationType.ORDER_UPDATE,
        subject=f'{label} — #{order.order_number}',
        body=f'El estado de tu orden #{order.order_number} cambio a: {label}.',
    )

    if user.email:
        user_email   = user.email
        name         = user.first_name or user.username
        order_num    = order.order_number
        shipping     = getattr(order, 'shipping_info', None)
        tracking_num = shipping.tracking_number if shipping else None
        transaction.on_commit(
            lambda: send_order_status_email_task.delay(
                user_email, name, order_num, new_status, tracking_num,
            )
        )


def notify_shipping_updated(order, user, tracking_number=None, event_description=None):
    """
    UC-NOT-03: notificacion de actualizacion de envio.
    Llamar desde apps.logistics dentro de transaction.atomic().
    """
    if not user or not getattr(user, 'pk', None):
        return

    Notification.objects.create(
        user=user,
        type=NotificationType.ORDER_UPDATE,
        subject=f'Actualizacion de envio — #{order.order_number}',
        body=event_description or f'Hay una actualizacion sobre el envio de tu orden #{order.order_number}.',
    )

    if user.email:
        user_email  = user.email
        name        = user.first_name or user.username
        order_num   = order.order_number
        tracking    = tracking_number
        description = event_description
        transaction.on_commit(
            lambda: send_shipping_update_email_task.delay(
                user_email, name, order_num, tracking, description,
            )
        )


def notify_return_processed(order, user, return_status, reason=None):
    """
    UC-NOT-04: notificacion de devolucion procesada.
    Llamar desde apps.returns dentro de transaction.atomic().
    """
    if not user or not getattr(user, 'pk', None):
        return

    _labels = {
        'APPROVED': 'Devolucion aprobada',
        'REJECTED': 'Devolucion rechazada',
    }
    label = _labels.get(return_status, f'Devolucion: {return_status}')

    Notification.objects.create(
        user=user,
        type=NotificationType.RETURN_UPDATE,
        subject=f'{label} — #{order.order_number}',
        body=f'Actualizacion sobre tu devolucion de la orden #{order.order_number}.',
    )

    if user.email:
        user_email   = user.email
        name         = user.first_name or user.username
        order_num    = order.order_number
        r_status     = return_status
        r_reason     = reason
        transaction.on_commit(
            lambda: send_return_processed_email_task.delay(
                user_email, name, order_num, r_status, r_reason,
            )
        )


def notify_refund_processed(order, user, amount_refunded):
    """
    UC-NOT-05: notificacion de reembolso procesado.
    Llamar desde apps.payments dentro de transaction.atomic().
    """
    if not user or not getattr(user, 'pk', None):
        return

    Notification.objects.create(
        user=user,
        type=NotificationType.RETURN_UPDATE,
        subject=f'Reembolso procesado — #{order.order_number}',
        body=f'Tu reembolso de ${amount_refunded} para la orden #{order.order_number} fue procesado.',
    )

    if user.email:
        user_email  = user.email
        name        = user.first_name or user.username
        order_num   = order.order_number
        amount      = str(amount_refunded)
        transaction.on_commit(
            lambda: send_refund_email_task.delay(
                user_email, name, order_num, amount,
            )
        )
