"""
Tests — Reenviar emails de notificacion fallidos (UC-SYS-04).

UC-SYS-04 es un proceso de sistema (sin endpoint HTTP): el management
command ``send_pending_emails`` drena la cola EmailTask (PENDING/RETRYING)
y reintenta con backoff exponencial (5 min x attempts), marcando FAILED al
agotar max_attempts.

Implementacion:
  apps/notifications/management/commands/send_pending_emails.py
  apps/notifications/models.py :: EmailTask
"""
import pytest
from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from apps.notifications.models import EmailTask

pytestmark = pytest.mark.integration


def _run():
    call_command('send_pending_emails')


class TestSendPendingEmails:

    def test_envia_pendiente_y_marca_sent(self, db):
        mail.outbox = []
        task = EmailTask.objects.create(
            to='dest@practicayoruba.mx',
            subject='Confirmacion de orden',
            body='Gracias por tu compra.',
            status=EmailTask.Status.PENDING,
        )
        _run()
        task.refresh_from_db()
        assert task.status == EmailTask.Status.SENT
        assert task.attempts == 1
        assert task.sent_at is not None
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ['dest@practicayoruba.mx']

    def test_no_procesa_tarea_futura(self, db):
        """scheduled_at en el futuro => no se toca (backoff aun pendiente)."""
        mail.outbox = []
        task = EmailTask.objects.create(
            to='futuro@practicayoruba.mx', subject='S', body='B',
            status=EmailTask.Status.RETRYING,
        )
        # auto_now_add fija scheduled_at; forzar al futuro con update.
        EmailTask.objects.filter(pk=task.pk).update(
            scheduled_at=timezone.now() + timedelta(hours=1),
        )
        _run()
        task.refresh_from_db()
        assert task.status == EmailTask.Status.RETRYING
        assert task.attempts == 0
        assert len(mail.outbox) == 0

    def test_fallo_de_envio_marca_retrying_con_backoff(self, db, settings):
        """Si send_mail lanza, la tarea pasa a RETRYING y reprograma scheduled_at."""
        settings.EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'
        task = EmailTask.objects.create(
            to='falla@practicayoruba.mx', subject='S', body='B',
            status=EmailTask.Status.PENDING, max_attempts=3,
        )
        before = timezone.now()
        with pytest.MonkeyPatch.context() as mp:
            def _boom(*a, **k):
                raise RuntimeError('SMTP down')
            mp.setattr(
                'apps.notifications.management.commands.send_pending_emails.send_mail',
                _boom,
            )
            _run()
        task.refresh_from_db()
        assert task.status == EmailTask.Status.RETRYING
        assert task.attempts == 1
        assert 'SMTP down' in task.last_error
        # backoff: scheduled_at corrido al futuro (5 min x attempts).
        assert task.scheduled_at > before

    def test_agota_reintentos_marca_failed(self, db):
        """Tras max_attempts fallos, la tarea queda FAILED (no se reintenta mas)."""
        task = EmailTask.objects.create(
            to='maxed@practicayoruba.mx', subject='S', body='B',
            status=EmailTask.Status.RETRYING, max_attempts=2, attempts=1,
        )
        with pytest.MonkeyPatch.context() as mp:
            def _boom(*a, **k):
                raise RuntimeError('SMTP down')
            mp.setattr(
                'apps.notifications.management.commands.send_pending_emails.send_mail',
                _boom,
            )
            _run()
        task.refresh_from_db()
        # attempts pasa de 1 a 2 == max_attempts => FAILED.
        assert task.attempts == 2
        assert task.status == EmailTask.Status.FAILED

    def test_no_reintenta_tarea_ya_enviada(self, db):
        mail.outbox = []
        task = EmailTask.objects.create(
            to='ya@practicayoruba.mx', subject='S', body='B',
            status=EmailTask.Status.SENT,
        )
        _run()
        task.refresh_from_db()
        assert task.status == EmailTask.Status.SENT
        assert len(mail.outbox) == 0
