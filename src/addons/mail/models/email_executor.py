"""
addons/mail/models/email_executor.py

Dispatcher asincrono para envio de emails — addon ``mail`` (fiel a Odoo, DEC-11).
Es el equivalente de ``mail.mail.process_email_queue`` de Odoo: envio async de
correo con cola de reintento, sin broker externo. El transporte SMTP se apoya en
la config de Django (``EMAIL_*``), analogo a ``ir.mail_server`` de ``addons/base``.

Alt 1 — ThreadPoolExecutor: envia el email en un hilo del pool, retornando
control inmediato al llamador HTTP. Elimina el bloqueo de 100-2000ms por
envio SMTP en los call sites de send_mail.

Alt 2 — EmailTask DB queue: si el envio falla en el thread, persiste la
tarea en EmailTask para reintento via management command send_pending_emails
(cron cada minuto). Garantia de entrega sin broker externo (sin Celery,
sin Redis, sin RabbitMQ). ``EmailTask`` vive hoy en ``addons.notifications``
(migrara a ``mail`` cuando ``notifications`` se disuelva).

UCs afectados: UC-NOT-01..05, UC-USR-02, UC-USR-04, UC-COM-01, UC-NEW-04.
"""
import logging
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings as _settings
from django.core.mail import send_mail as _send_mail

from addons.notifications.models import EmailTask

from .mail_notification import MailNotification

logger = logging.getLogger(__name__)

_pool = ThreadPoolExecutor(max_workers=4)


def dispatch_email(subject, message, from_email, recipient_list, *,
                   notification=None, **kwargs):
    """
    Envia email de forma asincrona via thread pool.

    Retorna inmediatamente. Si el envio falla, persiste en EmailTask
    para reintento automatico por send_pending_emails.

    No acepta fail_silently — los errores siempre se registran y persisten.

    En entornos de test (DISPATCH_EMAIL_SYNC=True) el envio es sincrono
    para que mail.outbox este poblado al momento de la asercion.

    ``notification`` (opcional): una ``mail.notification`` de canal email cuyo
    estado de entrega se actualiza segun el resultado — ``sent`` en exito, o
    ``exception`` + cross-link al ``EmailTask`` reencolado en fallo. Es el nexo
    fiel de Odoo entre la fila de entrega (``mail.notification``) y el correo
    saliente (``mail.mail``). ``None`` preserva el comportamiento previo (todos
    los llamadores actuales).
    """
    kwargs.pop('fail_silently', None)
    if getattr(_settings, 'DISPATCH_EMAIL_SYNC', False):
        try:
            _send_mail(subject, message, from_email, recipient_list, **kwargs)
        except Exception as exc:  # noqa: BLE001 — se registra y persiste, no se traga
            _finalize_failure(exc, subject, message, from_email, recipient_list,
                              notification)
        else:
            _mark_notification_sent(notification)
        return None
    future = _pool.submit(_send_mail, subject, message, from_email, recipient_list, **kwargs)
    future.add_done_callback(
        lambda f: _finalize_dispatch(f, subject, message, from_email,
                                     recipient_list, notification)
    )
    return future


def _finalize_dispatch(future, subject, message, from_email, recipient_list,
                       notification=None):
    exc = future.exception()
    if exc is None:
        _mark_notification_sent(notification)
        return
    _finalize_failure(exc, subject, message, from_email, recipient_list,
                      notification)


def _finalize_failure(exc, subject, message, from_email, recipient_list,
                      notification=None):
    logger.error('dispatch_email failed — persisting for retry: %s', exc)
    task = None
    try:
        if isinstance(recipient_list, (list, tuple)):
            to = ','.join(str(r) for r in recipient_list)
        else:
            to = str(recipient_list)
        task = EmailTask.objects.create(
            to=to[:500],
            subject=str(subject)[:255],
            body=str(message),
            from_email=str(from_email)[:254],
            last_error=str(exc)[:500],
            status=EmailTask.Status.RETRYING,
        )
    except Exception:
        logger.exception('Could not persist EmailTask for retry')
    _mark_notification_failed(notification, task, exc)


def _mark_notification_sent(notification):
    """Marca la ``mail.notification`` como entregada (Odoo status=sent)."""
    if notification is None:
        return
    notification.notification_status = MailNotification.STATUS_SENT
    notification.save(update_fields=['notification_status', 'updated_at'])


def _mark_notification_failed(notification, task, exc):
    """Marca la entrega como excepcion y la cruza con el ``EmailTask`` reencolado."""
    if notification is None:
        return
    notification.notification_status = MailNotification.STATUS_EXCEPTION
    notification.failure_type = MailNotification.FAILURE_MAIL_SMTP
    notification.failure_reason = str(exc)[:500]
    if task is not None:
        notification.email_task = task
    notification.save(update_fields=[
        'notification_status', 'failure_type', 'failure_reason',
        'email_task', 'updated_at',
    ])


def send_thread_email(record, partner, *, subject='', body='',
                      from_email=None, author=None):
    """Envia un mensaje del hilo de ``record`` a ``partner`` por correo y
    registra la entrega (Odoo ``_notify_thread`` canal email).

    Publica un ``mail.message`` de tipo email en el hilo (sin repartir a
    seguidores, ``notify=False``), crea una ``mail.notification`` de canal
    ``email`` para el destinatario, y despacha el correo enlazando esa
    notificacion — de modo que su estado (sent/exception) y su cross-link al
    ``EmailTask`` reflejen el resultado real del envio. Devuelve la
    ``MailNotification`` creada.
    """
    message = record.message_post(
        subject=subject, body=body, author=author,
        message_type='email', notify=False,
    )
    notification = MailNotification.objects.create(
        message=message, partner=partner,
        notification_type=MailNotification.TYPE_EMAIL,
        notification_status=MailNotification.STATUS_PROCESS,
    )
    dispatch_email(
        subject or (message.subject or ''),
        body or (message.body or ''),
        from_email or getattr(_settings, 'DEFAULT_FROM_EMAIL', None),
        [partner.email],
        notification=notification,
    )
    notification.refresh_from_db()
    return notification
