"""
Tests — Reenviar emails de notificacion fallidos (UC-SYS-04).

UC-SYS-04 es un proceso de sistema (sin endpoint HTTP): drena la cola de correo
saliente ``mail.mail`` (``MailMail``, hogar Odoo fiel de la ex-``EmailTask``):
filas ``outgoing`` cuya fecha diferida ya pasó, reintentando con backoff
exponencial (5 min x attempts) y marcando ``exception`` al agotar
``max_attempts``.

El ciclo lo corre el **cron** ``ir_cron_mail_scheduler``; el management command
es la entrada manual. Los tests siguen entrando por el comando porque ejercen el
mismo método —``MailMail.process_email_queue``— y de paso cubren que la
envoltura de CLI no se desconecte.

Por eso ``send_mail`` se parchea en ``addons.mail.models.mail_mail``: ahí vive
ahora la costura de envío. Parchearlo en el módulo del comando dejó de
funcionar cuando la lógica bajó al modelo, que es la señal correcta — el test
apuntaba a la implementación, no al contrato.

Implementacion:
  src/addons/mail/models/mail_mail.py :: MailMail.process_email_queue
  src/addons/mail/management/commands/send_pending_emails.py (envoltura)
"""
import pytest
from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from addons.mail.models import MailMail

pytestmark = pytest.mark.integration


def _run():
    call_command('send_pending_emails')


class TestSendPendingEmails:

    def test_envia_pendiente_y_marca_sent(self, db):
        mail.outbox = []
        m = MailMail.enqueue(
            to='dest@kaupamex.mx',
            subject='Confirmacion de orden',
            body_html='Gracias por tu compra.',
        )
        _run()
        m.refresh_from_db()
        assert m.state == MailMail.STATE_SENT
        assert m.attempts == 1
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ['dest@kaupamex.mx']

    def test_no_procesa_tarea_futura(self, db):
        """scheduled_date en el futuro => no se toca (backoff aun pendiente)."""
        mail.outbox = []
        m = MailMail.enqueue(
            to='futuro@kaupamex.mx', subject='S', body_html='B',
            scheduled_date=timezone.now() + timedelta(hours=1),
        )
        _run()
        m.refresh_from_db()
        assert m.state == MailMail.STATE_OUTGOING
        assert m.attempts == 0
        assert len(mail.outbox) == 0

    def test_fallo_de_envio_marca_retrying_con_backoff(self, db, settings):
        """Si send_mail lanza, el correo sigue outgoing y reprograma scheduled_date."""
        settings.EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'
        m = MailMail.enqueue(
            to='falla@kaupamex.mx', subject='S', body_html='B',
            max_attempts=3,
        )
        before = timezone.now()
        with pytest.MonkeyPatch.context() as mp:
            def _boom(*a, **k):
                raise RuntimeError('SMTP down')
            mp.setattr(
                'addons.mail.models.mail_mail.send_mail',
                _boom,
            )
            _run()
        m.refresh_from_db()
        assert m.state == MailMail.STATE_OUTGOING
        assert m.attempts == 1
        assert 'SMTP down' in m.failure_reason
        # backoff: scheduled_date corrido al futuro (5 min x attempts).
        assert m.scheduled_date > before

    def test_agota_reintentos_marca_failed(self, db):
        """Tras max_attempts fallos, el correo queda exception (no se reintenta mas)."""
        m = MailMail.enqueue(
            to='maxed@kaupamex.mx', subject='S', body_html='B',
            max_attempts=2,
        )
        MailMail.objects.filter(pk=m.pk).update(attempts=1)
        with pytest.MonkeyPatch.context() as mp:
            def _boom(*a, **k):
                raise RuntimeError('SMTP down')
            mp.setattr(
                'addons.mail.models.mail_mail.send_mail',
                _boom,
            )
            _run()
        m.refresh_from_db()
        # attempts pasa de 1 a 2 == max_attempts => exception.
        assert m.attempts == 2
        assert m.state == MailMail.STATE_EXCEPTION

    def test_no_reintenta_tarea_ya_enviada(self, db):
        mail.outbox = []
        m = MailMail.enqueue(
            to='ya@kaupamex.mx', subject='S', body_html='B',
        )
        m.mark_sent()
        _run()
        m.refresh_from_db()
        assert m.state == MailMail.STATE_SENT
        assert len(mail.outbox) == 0
