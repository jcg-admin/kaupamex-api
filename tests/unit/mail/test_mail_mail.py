"""TDD de ``mail.mail`` — cola de correo saliente (Odoo ``mail.mail``), hogar
fiel de ``notifications.EmailTask`` en disolucion.

Verifica el contrato del modelo portado: los 5 estados Odoo (outgoing/sent/
received/exception/cancel), el default ``outgoing``, el enqueue de la cola de
reintento, y las transiciones ``mark_sent``/``mark_exception``. La adaptacion de
proyecto (``attempts``/``max_attempts`` para el reintento sin broker) se ejercita
via ``should_retry`` y ``pending``.
"""
import pytest
from django.utils import timezone

from addons.mail.models import MailMail


class TestMailMailStates:
    def test_new_mail_defaults_to_outgoing(self, db):
        # ``subject`` NO es columna de ``mail.mail``: se delega al
        # ``mail.message`` enlazado (``_inherits`` de la referencia). El punto
        # de entrada que crea ambos es ``enqueue``; ``objects.create`` toca
        # sólo la tabla del correo y no puede recibirlo.
        m = MailMail.enqueue(to='a@x.com', subject='Hola')
        assert m.state == MailMail.STATE_OUTGOING
        assert m.attempts == 0
        assert m.max_attempts == 3
        assert m.failure_type is None
        assert m.scheduled_date is None

    def test_enqueue_creates_outgoing_row(self, db):
        m = MailMail.enqueue(
            to='a@x.com,b@x.com', subject='Promo',
            body_html='<p>hi</p>', email_from='no-reply@kaupamex.com',
        )
        assert m.pk is not None
        assert m.state == MailMail.STATE_OUTGOING
        assert m.email_to == 'a@x.com,b@x.com'
        assert m.email_from == 'no-reply@kaupamex.com'
        assert m.body_html == '<p>hi</p>'

    def test_mark_sent_transitions_to_sent(self, db):
        m = MailMail.enqueue(to='a@x.com', subject='X')
        m.mark_sent()
        m.refresh_from_db()
        assert m.state == MailMail.STATE_SENT

    def test_mark_exception_records_failure(self, db):
        m = MailMail.enqueue(to='a@x.com', subject='X')
        m.mark_exception(MailMail.FAILURE_MAIL_SMTP, 'SMTP down')
        m.refresh_from_db()
        assert m.state == MailMail.STATE_EXCEPTION
        assert m.failure_type == MailMail.FAILURE_MAIL_SMTP
        assert m.failure_reason == 'SMTP down'
        # marcar excepcion cuenta un intento
        assert m.attempts == 1


class TestMailMailRetryQueue:
    """Adaptacion de proyecto: cola de reintento sin broker (ex-EmailTask)."""

    def test_should_retry_while_under_max(self, db):
        m = MailMail.enqueue(to='a@x.com', subject='X')
        m.mark_exception(MailMail.FAILURE_MAIL_SMTP, 'boom')  # attempts=1
        m.refresh_from_db()
        assert m.state == MailMail.STATE_EXCEPTION
        # tras un fallo recuperable, se reencola a outgoing para reintento
        m.requeue()
        m.refresh_from_db()
        assert m.state == MailMail.STATE_OUTGOING
        assert m.should_retry is True

    def test_should_not_retry_at_max_attempts(self, db):
        m = MailMail.enqueue(to='a@x.com', subject='X')
        m.attempts = m.max_attempts
        m.save(update_fields=['attempts', 'updated_at'])
        assert m.should_retry is False

    def test_pending_returns_due_outgoing(self, db):
        due_now = MailMail.enqueue(to='a@x.com', subject='now')
        future = MailMail.enqueue(to='b@x.com', subject='later')
        future.scheduled_date = timezone.now() + timezone.timedelta(hours=1)
        future.save(update_fields=['scheduled_date', 'updated_at'])
        sent = MailMail.enqueue(to='c@x.com', subject='done')
        sent.mark_sent()

        pending_pks = set(MailMail.pending().values_list('pk', flat=True))
        assert due_now.pk in pending_pks
        assert future.pk not in pending_pks   # scheduled_date en el futuro
        assert sent.pk not in pending_pks      # ya enviado
