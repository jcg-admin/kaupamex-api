"""El fixture ``mock_smtplib_connection`` captura lo que ``send_email`` envía.

≙ ``odoo19c: odoo/addons/base/tests/common.py:378-451``.
"""
import pytest
from django.test import override_settings

from orm.environments import SUPERUSER_ID, Environment

pytestmark = pytest.mark.django_db


def _model():
    return Environment(uid=SUPERUSER_ID)['ir.mail_server']


@override_settings(DEFAULT_FROM_EMAIL='')
def test_send_email_is_captured_with_the_source_keys(mock_smtplib_connection):
    model = _model()
    message = model._build_email__(
        'ana@kaupamex.mx', ['bea@kaupamex.mx'], 'Hola', 'Cuerpo',
        email_cc=['cc@kaupamex.mx'])
    model.send_email(message)
    [sent] = mock_smtplib_connection.emails
    assert sent['msg_from'] == 'ana@kaupamex.mx'
    assert sent['msg_to'] == 'bea@kaupamex.mx'
    assert sent['msg_cc'] == 'cc@kaupamex.mx'
    assert sent['smtp_from'] == 'ana@kaupamex.mx'
    assert sorted(sent['smtp_to_list']) == [
        'bea@kaupamex.mx', 'cc@kaupamex.mx']
    assert 'Subject: Hola' in sent['message']
    assert mock_smtplib_connection.find_mail_server_mocked.called
    assert mock_smtplib_connection.connect_mocked.called


def test_without_the_fixture_nothing_is_sent():
    model = _model()
    message = model._build_email__(
        'ana@kaupamex.mx', ['bea@kaupamex.mx'], 'Hola', 'Cuerpo')
    assert model.send_email(message) == message['Message-Id']
