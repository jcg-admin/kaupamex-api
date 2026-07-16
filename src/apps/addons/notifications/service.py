"""
service.py — apps.addons.notifications
Servicios de notificacion transaccional. UC-NOT-01..05, UC-NOT-08.

Cada funcion `notify_*` hace dos cosas:
1. Crea la Notification in-app (debe llamarse dentro de transaction.atomic).
2. Despacha el email via transaction.on_commit (garantiza despacho solo si
   la transaccion commitea; se ejecuta sincronamente en el mismo proceso).

La separacion es intencional: in-app dentro de la transaccion mantiene
consistencia; email fuera evita enviar si el checkout/transicion falla.
No se usa Celery — el stack del proyecto no incluye broker de tareas.
"""
from django.db import transaction
from .models import Notification, NotificationType
from .emails import (
    send_order_confirmation_email,
    send_order_status_email,
    send_shipping_update_email,
    send_return_processed_email,
    send_refund_email,
    send_support_closed_email,
    send_support_created_email,
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
        name        = user.first_name or user.email
        order_num   = order.order_number
        total_str   = str(total_amount)
        transaction.on_commit(
            lambda: send_order_confirmation_email(
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
        'PROCESSING', 'IN_PREPARATION', 'SHIPPED',
        'DELIVERED', 'CANCELLED', 'REFUNDED',
    }
    if new_status not in notify_statuses:
        return

    user = getattr(order, 'user', None)
    if not user or not getattr(user, 'pk', None):
        return

    _labels = {
        'PROCESSING':      'Pago en proceso',
        'IN_PREPARATION':  'Pedido en preparacion',
        'SHIPPED':         'Pedido enviado',
        'DELIVERED':       'Pedido entregado',
        'CANCELLED':       'Orden cancelada',
        'REFUNDED':        'Orden reembolsada',
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
        name         = user.first_name or user.email
        order_num    = order.order_number
        shipping     = getattr(order, 'shipping_info', None)
        tracking_num = shipping.tracking_number if shipping else None
        transaction.on_commit(
            lambda: send_order_status_email(
                user_email, name, order_num, new_status, tracking_num,
            )
        )


def notify_shipping_updated(order, user, tracking_number=None, event_description=None):
    """
    UC-NOT-03: notificacion de actualizacion de envio.
    Llamar desde apps.addons.logistics dentro de transaction.atomic().
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
        name        = user.first_name or user.email
        order_num   = order.order_number
        tracking    = tracking_number
        description = event_description
        transaction.on_commit(
            lambda: send_shipping_update_email(
                user_email, name, order_num, tracking, description,
            )
        )


def notify_return_processed(order, user, return_status, reason=None):
    """
    UC-NOT-04: notificacion de devolucion procesada.
    Llamar desde apps.addons.returns dentro de transaction.atomic().
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
        name         = user.first_name or user.email
        order_num    = order.order_number
        r_status     = return_status
        r_reason     = reason
        transaction.on_commit(
            lambda: send_return_processed_email(
                user_email, name, order_num, r_status, r_reason,
            )
        )


def notify_return_info_requested(user, message, order_number=None):
    """UC-RET-02 AC-06 (b): notifica al comprador que el admin solicito
    informacion adicional sobre su devolucion.

    A diferencia de ``notify_return_processed``, no depende de un objeto
    ``Order`` cargado: la peticion la dispara el admin desde el endpoint
    request-info y el comprador debe enterarse aunque el snapshot de la
    orden no se resuelva. Llamar dentro de ``transaction.atomic()``.
    """
    if not user or not getattr(user, 'pk', None):
        return

    suffix = f' — #{order_number}' if order_number else ''
    Notification.objects.create(
        user=user,
        type=NotificationType.RETURN_UPDATE,
        subject=f'Informacion adicional solicitada{suffix}',
        body=(
            message
            or 'El equipo solicito informacion adicional sobre tu devolucion.'
        ),
    )


def notify_refund_processed(order, user, amount_refunded):
    """
    UC-NOT-05: notificacion de reembolso procesado.
    Llamar desde apps.addons.payments dentro de transaction.atomic().
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
        name        = user.first_name or user.email
        order_num   = order.order_number
        amount      = str(amount_refunded)
        transaction.on_commit(
            lambda: send_refund_email(
                user_email, name, order_num, amount,
            )
        )


def notify_support_closed(ticket, user, closed_by_staff=False):
    """
    UC-NOT-08: notificacion de cierre de ticket de soporte.
    Llamar dentro de transaction.atomic() post-transicion a CLOSED.
    Funciona para cierre manual (staff o buyer) y cierre automatico.
    """
    if not user or not getattr(user, 'pk', None):
        return

    if closed_by_staff:
        subject = f'Ticket #{ticket.pk} resuelto — Soporte'
        body = (
            f'Nuestro equipo ha marcado tu ticket #{ticket.pk} '
            f'"{ticket.subject}" como resuelto.'
        )
    else:
        subject = f'Ticket #{ticket.pk} cerrado'
        body = (
            f'Tu ticket #{ticket.pk} "{ticket.subject}" '
            f'ha sido cerrado.'
        )

    Notification.objects.create(
        user=user,
        type=NotificationType.SUPPORT_UPDATE,
        subject=subject,
        body=body,
    )

    if user.email:
        user_email   = user.email
        name         = user.first_name or user.email
        ticket_id    = ticket.pk
        ticket_subj  = ticket.subject
        by_staff     = closed_by_staff
        transaction.on_commit(
            lambda: send_support_closed_email(
                user_email, name, ticket_id, ticket_subj, by_staff,
            )
        )


def notify_support_created(ticket, user):
    """
    UC-SUPP-01 (POST-02/7.2): confirmacion de creacion de ticket de soporte.
    Llamar dentro de transaction.atomic() tras crear el ticket. Crea la
    Notification in-app y despacha el email de confirmacion al comprador
    (via on_commit; solo se envia si la transaccion commitea).

    H-18: antes la creacion de un ticket no notificaba nada; el UC exige el
    aviso al comprador (y al equipo). Aqui se cubre el aviso al comprador.
    """
    if not user or not getattr(user, 'pk', None):
        return

    Notification.objects.create(
        user=user,
        type=NotificationType.SUPPORT_UPDATE,
        subject=f'Ticket #{ticket.pk} creado',
        body=(
            f'Recibimos tu ticket #{ticket.pk} "{ticket.subject}". '
            f'Nuestro equipo te respondera a la brevedad.'
        ),
    )

    if user.email:
        user_email   = user.email
        name         = user.first_name or user.email
        ticket_id    = ticket.pk
        ticket_subj  = ticket.subject
        transaction.on_commit(
            lambda: send_support_created_email(
                user_email, name, ticket_id, ticket_subj,
            )
        )
