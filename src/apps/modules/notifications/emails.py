"""
emails.py — apps.modules.notifications
Funciones de envio de email transaccional. UC-NOT-01..05, UC-NOT-08.

No usa fail_silently=True — los errores se registran via logger
para cumplir POST-F01 (fallo siempre registrado, nunca silenciado).
"""
import logging
from django.conf import settings
from django.template.loader import render_to_string

from apps.core.email_executor import dispatch_email

logger = logging.getLogger(__name__)


def _render_transactional(heading, paragraphs, button_label=None,
                          button_url=None, preheader=None):
    """T-K: renderiza el correo transaccional HTML (emails/transactional.html,
    que extiende base.html) para tener un diseño nativo consistente con los
    correos de auth (reset/verify). Devuelve el HTML listo para html_message."""
    return render_to_string('emails/transactional.html', {
        'heading':      heading,
        'paragraphs':   paragraphs,
        'button_label': button_label,
        'button_url':   button_url,
        'preheader':    preheader or heading,
    })


def _from_email():
    return getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@practicayoruba.com')


def _frontend_url():
    return getattr(settings, 'FRONTEND_URL', 'http://localhost:3001')


def send_order_confirmation_email(user_email, user_name, order_number, order_total):
    """UC-NOT-01: confirmacion de orden creada (HTML nativo, T-K)."""
    subject = f'Orden confirmada #{order_number} — PracticaYoruba'
    order_url = f'{_frontend_url()}/account/orders/{order_number}'
    message = (
        f'Hola {user_name},\n\n'
        f'Recibimos tu orden #{order_number}. '
        f'El total de tu compra es ${order_total}.\n\n'
        f'Puedes ver el estado en:\n'
        f'{order_url}\n\n'
        f'Te notificaremos cuando tu pedido sea procesado.\n\n'
        f'— Equipo PracticaYoruba'
    )
    html_body = _render_transactional(
        heading=f'Orden confirmada #{order_number}',
        paragraphs=[
            f'Hola {user_name},',
            f'Recibimos tu orden #{order_number}. El total de tu compra es '
            f'${order_total}.',
            'Te notificaremos cuando tu pedido sea procesado.',
        ],
        button_label='Ver mi pedido',
        button_url=order_url,
        preheader=f'Recibimos tu orden #{order_number}.',
    )
    dispatch_email(
        subject=subject,
        message=message,
        from_email=_from_email(),
        recipient_list=[user_email],
        html_message=html_body,
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
    order_url = f'{_frontend_url()}/account/orders/{order_number}'
    message = (
        f'Hola {user_name},\n\n'
        f'{detail}\n\n'
        f'Ve el detalle en:\n'
        f'{order_url}\n\n'
        f'— Equipo PracticaYoruba'
    )
    html_body = _render_transactional(
        heading=title,
        paragraphs=[f'Hola {user_name},', detail],
        button_label='Ver mi pedido',
        button_url=order_url,
        preheader=detail,
    )
    dispatch_email(
        subject=subject,
        message=message,
        from_email=_from_email(),
        recipient_list=[user_email],
        html_message=html_body,
    )


def send_shipping_update_email(user_email, user_name, order_number, tracking_number=None, event_description=None):
    """UC-NOT-03: actualizacion de envio."""
    subject = f'Actualizacion de envio #{order_number} — PracticaYoruba'
    detail = event_description or 'Hay una actualizacion sobre el envio de tu pedido.'
    tracking_line = f'Numero de rastreo: {tracking_number}\n\n' if tracking_number else ''
    order_url = f'{_frontend_url()}/account/orders/{order_number}'
    message = (
        f'Hola {user_name},\n\n'
        f'{detail}\n\n'
        f'{tracking_line}'
        f'Ve el detalle en:\n'
        f'{order_url}\n\n'
        f'— Equipo PracticaYoruba'
    )
    paragraphs = [f'Hola {user_name},', detail]
    if tracking_number:
        paragraphs.append(f'Número de rastreo: {tracking_number}.')
    html_body = _render_transactional(
        heading='Actualización de tu envío',
        paragraphs=paragraphs,
        button_label='Ver mi pedido',
        button_url=order_url,
        preheader=detail,
    )
    dispatch_email(
        subject=subject,
        message=message,
        from_email=_from_email(),
        recipient_list=[user_email],
        html_message=html_body,
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
    returns_url = f'{_frontend_url()}/account/returns/'
    message = (
        f'Hola {user_name},\n\n'
        f'{detail}\n\n'
        f'Ve el detalle en:\n'
        f'{returns_url}\n\n'
        f'— Equipo PracticaYoruba'
    )
    html_body = _render_transactional(
        heading='Actualización de tu devolución',
        paragraphs=[f'Hola {user_name},', detail],
        button_label='Ver mis devoluciones',
        button_url=returns_url,
        preheader=detail,
    )
    dispatch_email(
        subject=subject,
        message=message,
        from_email=_from_email(),
        recipient_list=[user_email],
        html_message=html_body,
    )


def send_refund_email(user_email, user_name, order_number, amount_refunded):
    """UC-NOT-05: reembolso procesado."""
    subject = f'Reembolso procesado #{order_number} — PracticaYoruba'
    order_url = f'{_frontend_url()}/account/orders/{order_number}'
    message = (
        f'Hola {user_name},\n\n'
        f'Tu reembolso de ${amount_refunded} para la orden #{order_number} '
        f'ha sido procesado.\n\n'
        f'El monto aparecera en tu cuenta en 3-5 dias habiles.\n\n'
        f'— Equipo PracticaYoruba'
    )
    html_body = _render_transactional(
        heading='Reembolso procesado',
        paragraphs=[
            f'Hola {user_name},',
            f'Tu reembolso de ${amount_refunded} para la orden #{order_number} '
            f'ha sido procesado.',
            'El monto aparecerá en tu cuenta en 3-5 días hábiles.',
        ],
        button_label='Ver mi pedido',
        button_url=order_url,
        preheader=f'Reembolso de ${amount_refunded} procesado.',
    )
    dispatch_email(
        subject=subject,
        message=message,
        from_email=_from_email(),
        recipient_list=[user_email],
        html_message=html_body,
    )


def send_support_closed_email(user_email, user_name, ticket_id, ticket_subject, closed_by_staff=False):
    """UC-NOT-08: cierre de ticket de soporte."""
    if closed_by_staff:
        detail = (
            f'Nuestro equipo ha marcado tu ticket #{ticket_id} '
            f'"{ticket_subject}" como resuelto.'
        )
    else:
        detail = f'Tu ticket #{ticket_id} "{ticket_subject}" ha sido cerrado.'
    subject = f'Ticket de soporte #{ticket_id} cerrado — PracticaYoruba'
    new_ticket_url = f'{_frontend_url()}/support/tickets/new'
    message = (
        f'Hola {user_name},\n\n'
        f'{detail}\n\n'
        f'Si necesitas mas ayuda puedes abrir un nuevo ticket en:\n'
        f'{new_ticket_url}\n\n'
        f'— Equipo PracticaYoruba'
    )
    html_body = _render_transactional(
        heading=f'Ticket #{ticket_id} cerrado',
        paragraphs=[
            f'Hola {user_name},',
            detail,
            'Si necesitas más ayuda puedes abrir un nuevo ticket cuando quieras.',
        ],
        button_label='Abrir un nuevo ticket',
        button_url=new_ticket_url,
        preheader=detail,
    )
    dispatch_email(
        subject=subject,
        message=message,
        from_email=_from_email(),
        recipient_list=[user_email],
        html_message=html_body,
    )


def send_support_created_email(user_email, user_name, ticket_id, ticket_subject):
    """UC-SUPP-01 (POST-02/7.2): confirmacion de creacion de ticket (HTML nativo, T-K)."""
    subject = f'Ticket de soporte #{ticket_id} creado — PracticaYoruba'
    ticket_url = f'{_frontend_url()}/support/tickets/{ticket_id}'
    message = (
        f'Hola {user_name},\n\n'
        f'Recibimos tu ticket #{ticket_id} "{ticket_subject}". Nuestro equipo '
        f'de soporte lo revisara y te respondera a la brevedad.\n\n'
        f'Puedes seguir la conversacion en:\n'
        f'{ticket_url}\n\n'
        f'— Equipo PracticaYoruba'
    )
    html_body = _render_transactional(
        heading=f'Ticket #{ticket_id} creado',
        paragraphs=[
            f'Hola {user_name},',
            f'Recibimos tu ticket #{ticket_id} "{ticket_subject}". Nuestro '
            f'equipo de soporte lo revisará y te responderá a la brevedad.',
        ],
        button_label='Ver mi ticket',
        button_url=ticket_url,
        preheader=f'Recibimos tu ticket #{ticket_id}.',
    )
    dispatch_email(
        subject=subject,
        message=message,
        from_email=_from_email(),
        recipient_list=[user_email],
        html_message=html_body,
    )


def send_card_verification_email(user_email, user_name, verification_token, last_four):
    """
    Envía el email de verificación cuando un usuario guarda una nueva tarjeta.

    El enlace contiene el verification_token de un solo uso. Al hacer clic,
    el backend cambia SavedCard.status de pending_verification a active.
    El token expira implícitamente cuando la tarjeta es activada o eliminada.
    """
    verify_url = f'{_frontend_url()}/account/cards/verify/{verification_token}'
    subject = 'Activa tu tarjeta guardada — PracticaYoruba'
    message = (
        f'Hola {user_name},\n\n'
        f'Recibimos una solicitud para guardar la tarjeta terminada en {last_four} '
        f'en tu cuenta de PracticaYoruba.\n\n'
        f'Para activarla y usarla en tus próximos pagos, haz clic en el '
        f'siguiente enlace:\n\n'
        f'  {verify_url}\n\n'
        f'Si no reconoces esta acción, ignora este mensaje. Tu tarjeta no '
        f'será activada y puedes continuar usando tu cuenta con normalidad.\n\n'
        f'Por seguridad, este enlace es de un solo uso. Una vez activada la '
        f'tarjeta, el enlace dejará de funcionar.\n\n'
        f'— Equipo PracticaYoruba'
    )
    html_body = _render_transactional(
        heading='Activa tu tarjeta guardada',
        paragraphs=[
            f'Hola {user_name},',
            f'Recibimos una solicitud para guardar la tarjeta terminada en '
            f'{last_four} en tu cuenta de PracticaYoruba.',
            'Si no reconoces esta acción, ignora este mensaje: tu tarjeta no '
            'será activada. Por seguridad, este enlace es de un solo uso.',
        ],
        button_label='Activar mi tarjeta',
        button_url=verify_url,
        preheader=f'Activa la tarjeta terminada en {last_four}.',
    )
    dispatch_email(
        subject=subject,
        message=message,
        from_email=_from_email(),
        recipient_list=[user_email],
        html_message=html_body,
    )
