"""El envío y la prueba de conexión de ``ir.mail_server``.

≙ ``odoo19c: odoo/addons/base/models/ir_mail_server.py``:
``extract_rfc2822_addresses`` (``:105-119``), ``_get_test_email_from``
(``:280-295``), ``_get_test_email_to`` (``:297-298``),
``test_smtp_connection`` (``:300-382``), ``action_retrieve_max_email_size``
(``:384-386``) y ``send_email`` (``:798-868``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
base-ir-mail-server-complete.md``, paso 3c.
"""
import smtplib
from types import SimpleNamespace
from unittest import mock

import pytest
from django.test import override_settings

from addons.base.models import ir_mail_server as module
from addons.base.models.ir_mail_server import (
    IrMailServer,
    MailDeliveryException,
    extract_rfc2822_addresses,
)
from exceptions import UserError
from orm.environments import SUPERUSER_ID, Environment, sudo
from tools.mail import formataddr

pytestmark = pytest.mark.django_db


def _model():
    return Environment(uid=SUPERUSER_ID)['ir.mail_server']


def _message():
    return _model()._build_email__(
        'ana@kaupamex.mx', ['bea@kaupamex.mx'], 'Hola', 'Cuerpo')


class FakeSession:
    """Una sesión SMTP ya abierta que registra lo que se le pide."""

    def __init__(self, fail_with=None, replies=None, size=None):
        self.from_filter = False
        self.smtp_from = False
        self.fail_with = fail_with
        self.replies = replies or {}
        self.esmtp_features = {'size': size} if size else {}
        self.calls = []

    def send_message(self, message, smtp_from, smtp_to_list):
        if self.fail_with:
            raise self.fail_with
        self.calls.append(('send', smtp_from, smtp_to_list))

    def quit(self):
        self.calls.append(('quit',))

    def mail(self, email_from):
        self.calls.append(('mail', email_from))
        return self.replies.get('mail', (250, b'ok'))

    def rcpt(self, email_to):
        self.calls.append(('rcpt', email_to))
        return self.replies.get('rcpt', (250, b'ok'))

    def putcmd(self, cmd):
        self.calls.append(('putcmd', cmd))

    def getreply(self):
        return self.replies.get('data', (354, b'go'))

    def close(self):
        self.calls.append(('close',))


@pytest.fixture
def sending(monkeypatch):
    monkeypatch.setattr(IrMailServer, '_disable_send',
                        classmethod(lambda cls: False))


# --- extract_rfc2822_addresses ---------------------------------------------

def test_an_international_address_is_kept_idna_encoded():
    assert extract_rfc2822_addresses('Ana <ana@bücher.mx>') == [
        formataddr(('', 'ana@bücher.mx'), charset='ascii')]


def test_an_address_idna_cannot_encode_is_dropped():
    bad = 'a@' + 'ü' * 70 + '.mx'
    assert extract_rfc2822_addresses(f'{bad}, bea@kaupamex.mx') == [
        'bea@kaupamex.mx']


# --- _get_test_email_from / _get_test_email_to -----------------------------

def test_the_test_recipient_is_the_source_one():
    assert IrMailServer()._get_test_email_to() == 'noreply@odoo.com'


def test_without_filter_the_test_sender_is_the_current_user():
    user = SimpleNamespace(email='yo@kaupamex.mx')
    with mock.patch.object(Environment, 'user', new_callable=mock.PropertyMock,
                           return_value=user):
        assert IrMailServer(from_filter='')._get_test_email_from() == (
            'yo@kaupamex.mx')


def test_without_filter_nor_user_email_the_test_sender_is_refused():
    user = SimpleNamespace(email=False)
    with mock.patch.object(Environment, 'user', new_callable=mock.PropertyMock,
                           return_value=user):
        with pytest.raises(UserError) as error:
            IrMailServer(from_filter='')._get_test_email_from()
    assert str(error.value).startswith('Please configure an email')


# --- send_email ------------------------------------------------------------

def test_under_tests_send_email_returns_the_id_without_sending():
    message = _message()
    session = FakeSession()
    assert _model().send_email(message, smtp_session=session) == (
        message['Message-Id'])
    assert session.calls == []


@override_settings(DEFAULT_FROM_EMAIL='')
def test_send_email_sends_through_the_given_session(sending):
    message = _message()
    session = FakeSession()
    assert _model().send_email(message, smtp_session=session) == (
        message['Message-Id'])
    assert session.calls == [
        ('send', 'ana@kaupamex.mx', ['bea@kaupamex.mx'])]


def test_send_email_quits_the_session_it_opened(sending, monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(IrMailServer, '_connect__',
                        lambda self, *a, **k: session)
    _model().send_email(_message())
    assert session.calls[-1] == ('quit',)


def test_a_delivery_error_becomes_mail_delivery_exception(sending):
    session = FakeSession(fail_with=smtplib.SMTPRecipientsRefused({}))
    with pytest.raises(MailDeliveryException) as error:
        _model().send_email(_message(), smtp_session=session)
    assert 'Mail Delivery Failed' in str(error.value)


def test_a_server_disconnection_is_reraised(sending):
    session = FakeSession(fail_with=smtplib.SMTPServerDisconnected('x'))
    with pytest.raises(smtplib.SMTPServerDisconnected):
        _model().send_email(_message(), smtp_session=session)


# --- test_smtp_connection --------------------------------------------------

def _server(**values):
    with sudo():
        return IrMailServer.create({
            'name': 'smtp', 'smtp_host': 'smtp.kaupamex.mx',
            'from_filter': 'ana@kaupamex.mx', **values})


def test_a_successful_connection_test_notifies(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(IrMailServer, '_connect__',
                        lambda self, *a, **k: session)
    server = _server()
    with sudo():
        action = server.test_smtp_connection()
    assert action['params']['message'] == 'Connection Test Successful!'
    assert ('mail', 'ana@kaupamex.mx') in session.calls
    assert ('rcpt', 'noreply@odoo.com') in session.calls
    assert ('putcmd', 'data') in session.calls
    assert session.calls[-1] == ('close',)


def test_a_refused_sender_is_reported(monkeypatch):
    session = FakeSession(replies={'mail': (550, b'no')})
    monkeypatch.setattr(IrMailServer, '_connect__',
                        lambda self, *a, **k: session)
    with sudo(), pytest.raises(UserError) as error:
        _server().test_smtp_connection()
    assert str(error.value).startswith('The server refused the sender')


def test_a_disconnection_during_the_test_is_explained(monkeypatch):
    def connect(self, *args, **kwargs):
        raise smtplib.SMTPServerDisconnected('cerrado')
    monkeypatch.setattr(IrMailServer, '_connect__', connect)
    with sudo(), pytest.raises(UserError) as error:
        _server().test_smtp_connection()
    assert str(error.value).startswith(
        'The server has closed the connection unexpectedly')


def test_retrieving_the_max_size_stores_it(monkeypatch):
    session = FakeSession(size=str(25 * 1024 ** 2))
    monkeypatch.setattr(IrMailServer, '_connect__',
                        lambda self, *a, **k: session)
    server = _server()
    with sudo():
        action = server.action_retrieve_max_email_size()
    assert IrMailServer.objects.get(pk=server.pk).max_email_size == 25.0
    assert action['params']['message'].startswith(
        'Email maximum size updated')


def test_test_logger_is_the_source_one():
    assert module._test_logger.name == 'odoo.tests'
