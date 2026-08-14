"""Servicio de SMS del hilo — addon ``sms`` (canal SMS del backbone ``mail``).

Analogo al canal email de ``mail.email_executor``: al enviar un SMS sobre el
hilo de un registro se materializan (a) la intencion de envio ``sms.sms`` y
(b) su fila de entrega ``mail.notification`` de canal ``sms``, cruzadas entre
si. El **transporte real** (IAP de Odoo / gateway SMS) queda fuera de scope
(Clausula 5 anti-performativa — no se fabrica el gateway); lo que se porta es
la relacion y su maquina de estados, que el proveedor que se integre despues
acciona con ``mark_sms_sent`` / ``mark_sms_error``.

Direccion de acoplamiento: ``sms`` importa ``mail`` (el backbone nunca importa
``sms`` — usa string FK ``'sms.SmsSms'``).
"""
from addons.mail.models import MailMessage, MailNotification

from .models import SmsSms


def send_thread_sms(record, partner, *, body='', number=None, author=None):
    """Registra el envio de un SMS sobre el hilo de ``record`` a ``partner``.

    Publica un ``mail.message`` de tipo notification en el hilo (sin repartir a
    seguidores), crea la intencion ``sms.sms`` (estado ``pending``) y la fila de
    entrega ``mail.notification`` de canal ``sms`` cruzada con ella. Devuelve la
    ``MailNotification`` creada (estado ``process`` hasta que el transporte la
    resuelva). El numero sale de ``number`` o del ``phone`` del destinatario.
    """
    message = record.message_post(
        body=body, message_type=MailMessage.TYPE_NOTIFICATION,
        author=author, notify=False,
    )
    sms = SmsSms.objects.create(
        number=number or getattr(partner, 'phone', '') or '',
        body=body,
        state=SmsSms.STATE_PENDING,
    )
    return MailNotification.objects.create(
        message=message, partner=partner,
        notification_type=MailNotification.TYPE_SMS,
        notification_status=MailNotification.STATUS_PROCESS,
        sms=sms,
    )


def mark_sms_sent(notification):
    """El transporte confirma la entrega: ``sms.sms`` → sent, entrega → sent."""
    if notification.sms_id:
        notification.sms.mark_sent()
    notification.notification_status = MailNotification.STATUS_SENT
    notification.save(update_fields=['notification_status', 'updated_at'])


def mark_sms_error(notification, reason, failure_type=None):
    """El transporte reporta un fallo: ``sms.sms`` → error, entrega → exception."""
    if notification.sms_id:
        notification.sms.mark_error(str(reason)[:64])
    notification.notification_status = MailNotification.STATUS_EXCEPTION
    notification.failure_type = failure_type or MailNotification.FAILURE_UNKNOWN
    notification.failure_reason = str(reason)[:500]
    notification.save(update_fields=[
        'notification_status', 'failure_type', 'failure_reason', 'updated_at',
    ])
