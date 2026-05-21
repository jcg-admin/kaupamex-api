"""
emails.py — apps.notifications
Funciones de envio de email transaccional. UC-NOT-01..05.

No usa fail_silently=True — los errores se registran via logger
para cumplir POST-F01 (fallo siempre registrado, nunca silenciado).
"""
import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _from_email():
    return getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@practicayoruba.mx')


def _frontend_url():
    return getattr(settings, 'FRONTEND_URL', 'http://localhost:3001')


def send_order_confirmation_email(user_email, user_name, order_number, order_total):
    """UC-NOT-01: confirmacion de orden creada."""
    subject = f'Orden confirmada #{order_number} — PracticaYoruba'
    message = (
        f'Hola {user_name},\n\n'
        f'Recibimos tu orden #{order_number}. '
        f'El total de tu compra es ${order_total}.\n\n'
        f'Puedes ver el estado en:\n'
        f'{_frontend_url()}/account/orders/{order_number}\n\n'
        f'Te notificaremos cuando tu pedido sea procesado.\n\n'
        f'— Equipo PracticaYoruba'
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=_from_email(),
            recipient_list=[user_email],
            fail_silently=False,
        )
    except Exception:
        logger.error(
            'UC-NOT-01: fallo envio email confirmacion order=%s email=%s',
            order_number, user_email, exc_info=True,
        )


def send_order_status_email(user_email, user_name, order_number, new_status, tracking_number=None):
    """UC-NOT-02: cambio de estado de orden."""
    _labels = {
        'PAYMENT_CONFIRMED': ('Pago confirmado', 'El pago fue confirmado. Estamos preparando tu pedido.'),
        'IN_PREPARATION':    ('Pedido en preparacion', 'Tu pedido esta siendo preparado.'),
        'SHIPPED':           ('Pedido enviado', 'Tu pedido ha sido enviado.'),
        'DELIVERED':         ('Pedido entregado', '¡Tu pedido fue entregado! Esperamos que lo disfrutes.'),
        'CANCELLED':         ('Orden cancelada', 'Tu orden fue cancelada.'),
        'CANCELLED_TIMEOUT': ('Orden cancelada', 'Tu orden fue cancelada por tiempo de pago agotado.'),
    }
    title, detail = _labels.get(new_status, ('Actualizacion de orden', f'Estado: {new_status}'))
    if new_status == 'SHIPPED' and tracking_number:
        detail += f' Numero de rastreo: {tracking_number}.'
    subject = f'{title} — #{order_number} — PracticaYoruba'
    message = (
        f'Hola {user_name},\n\n'
        f'{detail}\n\n'
        f'Ve el detalle en:\n'
        f'{_frontend_url()}/account/orders/{order_number}\n\n'
        f'— Equipo PracticaYoruba'
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=_from_email(),
            recipient_list=[user_email],
            fail_silently=False,
        )
    except Exception:
        logger.error(
            'UC-NOT-02: fallo envio email estado order=%s status=%s',
            order_number, new_status, exc_info=True,
        )


def send_shipping_update_email(user_email, user_name, order_number, tracking_number=None, event_description=None):
    """UC-NOT-03: actualizacion de envio."""
    subject = f'Actualizacion de envio #{order_number} — PracticaYoruba'
    detail = event_description or 'Hay una actualizacion sobre el envio de tu pedido.'
    tracking_line = f'Numero de rastreo: {tracking_number}\n\n' if tracking_number else ''
    message = (
        f'Hola {user_name},\n\n'
        f'{detail}\n\n'
        f'{tracking_line}'
        f'Ve el detalle en:\n'
        f'{_frontend_url()}/account/orders/{order_number}\n\n'
        f'— Equipo PracticaYoruba'
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=_from_email(),
            recipient_list=[user_email],
            fail_silently=False,
        )
    except Exception:
        logger.error(
            'UC-NOT-03: fallo envio email shipping order=%s',
            order_number, exc_info=True,
        )


def send_return_processed_email(user_email, user_name, order_number, return_status, reason=None):
    """UC-NOT-04: devolucion procesada."""
    if return_status == 'APPROVED':
        detail = (
            f'Tu solicitud de devolucion para la orden #{order_number} fue aprobada. '
            f'Procesaremos el reembolso en breve.'
        )
    elif return_status == 'REJECTED':
        reason_text = f' Motivo: {reason}.' if reason else ''
        detail = f'Tu solicitud de devolucion para la orden #{order_number} fue rechazada.{reason_text}'
    else:
        detail = f'Actualizacion sobre tu devolucion de la orden #{order_number}: {return_status}.'
    subject = f'Actualizacion de devolucion #{order_number} — PracticaYoruba'
    message = (
        f'Hola {user_name},\n\n'
        f'{detail}\n\n'
        f'Ve el detalle en:\n'
        f'{_frontend_url()}/account/returns/\n\n'
        f'— Equipo PracticaYoruba'
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=_from_email(),
            recipient_list=[user_email],
            fail_silently=False,
        )
    except Exception:
        logger.error(
            'UC-NOT-04: fallo envio email devolucion order=%s',
            order_number, exc_info=True,
        )


def send_refund_email(user_email, user_name, order_number, amount_refunded):
    """UC-NOT-05: reembolso procesado."""
    subject = f'Reembolso procesado #{order_number} — PracticaYoruba'
    message = (
        f'Hola {user_name},\n\n'
        f'Tu reembolso de ${amount_refunded} para la orden #{order_number} '
        f'ha sido procesado.\n\n'
        f'El monto aparecera en tu cuenta en 3-5 dias habiles.\n\n'
        f'— Equipo PracticaYoruba'
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=_from_email(),
            recipient_list=[user_email],
            fail_silently=False,
        )
    except Exception:
        logger.error(
            'UC-NOT-05: fallo envio email reembolso order=%s',
            order_number, exc_info=True,
        )
