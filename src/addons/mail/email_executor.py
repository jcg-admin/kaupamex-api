"""
addons/mail/email_executor.py

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

logger = logging.getLogger(__name__)

_pool = ThreadPoolExecutor(max_workers=4)


def dispatch_email(subject, message, from_email, recipient_list, **kwargs):
    """
    Envia email de forma asincrona via thread pool.

    Retorna inmediatamente. Si el envio falla, persiste en EmailTask
    para reintento automatico por send_pending_emails.

    No acepta fail_silently — los errores siempre se registran y persisten.

    En entornos de test (DISPATCH_EMAIL_SYNC=True) el envio es sincrono
    para que mail.outbox este poblado al momento de la asercion.
    """
    kwargs.pop('fail_silently', None)
    if getattr(_settings, 'DISPATCH_EMAIL_SYNC', False):
        _send_mail(subject, message, from_email, recipient_list, **kwargs)
        return None
    future = _pool.submit(_send_mail, subject, message, from_email, recipient_list, **kwargs)
    future.add_done_callback(
        lambda f: _persist_if_failed(f, subject, message, from_email, recipient_list)
    )
    return future


def _persist_if_failed(future, subject, message, from_email, recipient_list):
    exc = future.exception()
    if exc is None:
        return
    logger.error('dispatch_email failed — persisting for retry: %s', exc)
    try:
        if isinstance(recipient_list, (list, tuple)):
            to = ','.join(str(r) for r in recipient_list)
        else:
            to = str(recipient_list)
        EmailTask.objects.create(
            to=to[:500],
            subject=str(subject)[:255],
            body=str(message),
            from_email=str(from_email)[:254],
            last_error=str(exc)[:500],
            status=EmailTask.Status.RETRYING,
        )
    except Exception:
        logger.exception('Could not persist EmailTask for retry')
