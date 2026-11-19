"""La conexión SMTP de ``ir.mail_server``.

≙ ``odoo19c: odoo/addons/base/models/ir_mail_server.py``: los parches al
importar (``:68-98``), ``_verify_check_hostname_callback`` (``:122-137``),
``_disable_send`` (``:388-392``), ``_connect__`` (``:394-534``) y
``_smtp_login__`` (``:541-551``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
base-ir-mail-server-complete.md``, paso 3b.
"""
import datetime
import email.policy
import smtplib
from email.message import EmailMessage

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from django.test import override_settings
from OpenSSL import crypto

from addons.base.models import ir_mail_server as module
from addons.base.models.ir_mail_server import IrMailServer
from exceptions import UserError
from orm.environments import SUPERUSER_ID, Environment, sudo

pytestmark = pytest.mark.django_db


class FakeSMTP:
    """Doble de ``smtplib.SMTP``: registra lo que la conexión le pide."""

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.timeout = host, port, timeout
        self.calls = []

    def set_debuglevel(self, level):
        self.calls.append(('debug', level))

    def starttls(self, context=None):
        self.calls.append(('starttls',))

    def login(self, user, password):
        self.calls.append(('login', user, password))

    def ehlo_or_helo_if_needed(self):
        self.calls.append(('ehlo',))


@pytest.fixture
def sending(monkeypatch):
    """Envío habilitado y ``smtplib.SMTP`` sustituido por el doble."""
    monkeypatch.setattr(IrMailServer, '_disable_send',
                        classmethod(lambda cls: False))
    monkeypatch.setattr(module.smtplib, 'SMTP', FakeSMTP)


def _model():
    return Environment(uid=SUPERUSER_ID)['ir.mail_server']


def test_no_connection_is_made_under_tests():
    assert IrMailServer._disable_send() is True
    assert _model()._connect__(host='smtp.kaupamex.mx') is None


def test_the_server_record_drives_the_connection(sending):
    with sudo():
        server = IrMailServer.create({
            'name': 'smtp', 'smtp_host': 'smtp.kaupamex.mx',
            'smtp_port': 2525, 'smtp_user': 'ana@kaupamex.mx',
            'smtp_pass': 'secreto', 'smtp_encryption': 'none',
            'from_filter': 'kaupamex.mx',
        })
        connection = _model()._connect__(
            mail_server_id=server.id, smtp_from='ana@kaupamex.mx')
    assert (connection.host, connection.port) == ('smtp.kaupamex.mx', 2525)
    assert connection.timeout == module.SMTP_TIMEOUT
    assert ('login', 'ana@kaupamex.mx', 'secreto') in connection.calls
    assert ('starttls',) not in connection.calls
    assert connection.calls[-1] == ('ehlo',)
    assert connection.from_filter == 'kaupamex.mx'
    assert connection.smtp_from == 'ana@kaupamex.mx'


@override_settings(EMAIL_HOST='smtp.config.mx', EMAIL_PORT=587,
                   EMAIL_USE_TLS=True, EMAIL_HOST_USER='',
                   EMAIL_FROM_FILTER='config.mx')
def test_without_a_server_the_config_drives_the_connection(sending):
    IrMailServer.objects.all().delete()
    connection = _model()._connect__(smtp_from='ana@config.mx')
    assert (connection.host, connection.port) == ('smtp.config.mx', 587)
    assert ('starttls',) in connection.calls
    assert not [call for call in connection.calls if call[0] == 'login']
    assert connection.from_filter == 'config.mx'


def test_an_international_login_domain_is_idna_encoded(sending):
    connection = _model()._connect__(
        host='smtp.kaupamex.mx', port=25, user='ana@bücher.mx',
        password='p')
    assert ('login', 'ana@xn--bcher-kva.mx', 'p') in connection.calls


def test_a_missing_smtp_server_is_refused(sending, monkeypatch):
    IrMailServer.objects.all().delete()
    monkeypatch.setattr(module.config, 'smtp_server', lambda: '')
    with pytest.raises(UserError) as error:
        _model()._connect__()
    assert str(error.value).startswith('Missing SMTP Server')


def test_the_import_time_patches_are_applied():
    assert smtplib.SMTP._print_debug is module._print_debug
    assert isinstance(smtplib.stderr, module.WriteToLogger)
    assert isinstance(email.policy.SMTP,
                      module.IdentificationFieldsNoFoldPolicy)


def test_a_long_user_header_is_not_folded():
    """``Subject`` va con ``max_line_length=998`` (``:76,87-88``)."""
    message = EmailMessage(policy=email.policy.SMTP)
    subject = ' '.join(['palabra'] * 15)
    message['Subject'] = subject
    assert f'Subject: {subject}\r\n' in message.as_string()


def _certificate(common_name):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(1)
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName(
                [x509.DNSName(common_name)]), critical=False)
            .sign(key, hashes.SHA256()))
    return crypto.X509.from_cryptography(cert)


def test_the_hostname_callback_checks_the_leaf_certificate():
    callback = module._verify_check_hostname_callback
    leaf = _certificate('smtp.kaupamex.mx')
    assert callback(None, leaf, 1, 0, 0, hostname='smtp.kaupamex.mx') is False
    assert callback(None, leaf, 0, 1, 1, hostname='otro.mx') is True
    assert callback(None, leaf, 0, 0, 1, hostname='smtp.kaupamex.mx') is True
    with pytest.raises(module.CertificateError):
        callback(None, leaf, 0, 0, 1, hostname='otro.mx')
