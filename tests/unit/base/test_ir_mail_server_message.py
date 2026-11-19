"""La construcción y preparación del mensaje de ``ir.mail_server``.

≙ ``odoo19c: odoo/addons/base/models/ir_mail_server.py``: las constantes de
error (``:147-154``), ``_build_email__`` (``:562-644``),
``_prepare_email_message__`` (``:679-733``), ``_alter_message__``
(``:735-762``) y ``_prepare_smtp_to_list`` (``:764-797``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
base-ir-mail-server-complete.md``, paso 3, familia del mensaje.
"""
import pytest
from django.test import override_settings

from addons.base.models.ir_mail_server import IrMailServer
from orm.environments import SUPERUSER_ID, Environment

pytestmark = pytest.mark.django_db


def _model(**context):
    """``env['ir.mail_server']``, vacío y con el contexto pedido."""
    return Environment(uid=SUPERUSER_ID)['ir.mail_server'].with_context(
        **context)


def test_the_error_messages_are_the_source_ones():
    assert IrMailServer.NO_VALID_RECIPIENT.startswith(
        'At least one valid recipient address')
    assert IrMailServer.NO_FOUND_SMTP_FROM == (
        'The Return-Path or From header is required for any outbound email')
    assert IrMailServer.NO_VALID_FROM.startswith(
        "Malformed 'Return-Path' or 'From' address")
    assert IrMailServer.NO_FOUND_FROM.startswith(
        'You must either provide a sender address explicitly')


def test_build_email_sets_the_headers():
    msg = _model()._build_email__(
        'ana@kaupamex.mx', ['bea@kaupamex.mx'], 'Hola', 'Cuerpo',
        email_cc=['cc@kaupamex.mx'], email_bcc=['bcc@kaupamex.mx'],
        headers={'X-Custom': 'uno'})
    assert msg['From'] == 'ana@kaupamex.mx'
    assert msg['Reply-To'] == 'ana@kaupamex.mx'
    assert msg['To'] == 'bea@kaupamex.mx'
    assert msg['Cc'] == 'cc@kaupamex.mx'
    assert msg['Bcc'] == 'bcc@kaupamex.mx'
    assert msg['Subject'] == 'Hola'
    assert msg['X-Custom'] == 'uno'
    assert msg['Message-Id']
    assert msg.get_content().strip() == 'Cuerpo'


def test_build_email_tracks_the_object_in_the_message_id():
    msg = _model()._build_email__(
        'ana@kaupamex.mx', ['bea@kaupamex.mx'], 'Hola', 'Cuerpo',
        object_id='12-crm.lead')
    assert '12-crm.lead' in msg['Message-Id']


def test_an_html_body_gets_a_plain_alternative():
    msg = _model()._build_email__(
        'ana@kaupamex.mx', ['bea@kaupamex.mx'], 'Hola',
        '<p>Hola <b>Bea</b></p>',
        subtype='html')
    assert msg.get_content_type() == 'multipart/alternative'
    plain, html = msg.get_payload()
    assert plain.get_content_type() == 'text/plain'
    assert 'Hola' in plain.get_content()
    assert html.get_content_type() == 'text/html'


def test_attachments_keep_their_mime_type():
    msg = _model()._build_email__(
        'ana@kaupamex.mx', ['bea@kaupamex.mx'], 'Hola', 'Cuerpo',
        attachments=[('a.txt', b'hola', 'text/plain')])
    parts = [part for part in msg.iter_attachments()]
    assert [(p.get_filename(), p.get_content_type()) for p in parts] == [
        ('a.txt', 'text/plain')]


@override_settings(DEFAULT_FROM_EMAIL='')
def test_without_any_sender_the_message_is_refused():
    with pytest.raises(AssertionError, match='sender address explicitly'):
        _model()._build_email__(False, ['bea@kaupamex.mx'], 'Hola', 'Cuerpo')


def test_the_smtp_recipients_join_to_cc_and_bcc_once():
    msg = _model()._build_email__(
        'ana@kaupamex.mx', ['bea@kaupamex.mx', 'bea@kaupamex.mx'], 'Hola',
        'Cuerpo', email_cc=['cc@kaupamex.mx'], email_bcc=['bcc@kaupamex.mx'])
    assert _model()._prepare_smtp_to_list(msg, None) == [
        'bea@kaupamex.mx', 'cc@kaupamex.mx', 'bcc@kaupamex.mx']


def test_the_recipients_honour_the_validated_and_skip_lists():
    msg = _model()._build_email__(
        'ana@kaupamex.mx', ['bea@kaupamex.mx', 'cid@kaupamex.mx'], 'Hola',
        'Cuerpo')
    assert _model(send_validated_to=['bea@kaupamex.mx'])._prepare_smtp_to_list(
        msg, None) == ['bea@kaupamex.mx']
    assert _model(send_smtp_skip_to=['bea@kaupamex.mx'])._prepare_smtp_to_list(
        msg, None) == ['cid@kaupamex.mx']


def test_alter_message_forges_to_and_drops_bcc():
    msg = _model()._build_email__(
        'ana@kaupamex.mx', ['bea@kaupamex.mx'], 'Hola', 'Cuerpo',
        email_bcc=['bcc@kaupamex.mx'],
        headers={'X-Forge-To': 'canal@kaupamex.mx'})
    _model()._alter_message__(msg, 'envio@kaupamex.mx', ['bea@kaupamex.mx'])
    assert msg['To'] == 'canal@kaupamex.mx'
    assert msg['From'] == 'envio@kaupamex.mx'
    assert msg['Bcc'] is None
    assert msg['X-Forge-To'] is None


def test_prepare_uses_the_return_path_as_envelope_sender():
    msg = _model()._build_email__(
        'ana@kaupamex.mx', ['bea@kaupamex.mx'], 'Hola', 'Cuerpo',
        headers={'Return-Path': 'rebote@kaupamex.mx'})
    smtp_from, smtp_to, _msg = _model()._prepare_email_message__(msg, None)
    assert smtp_from == 'rebote@kaupamex.mx'
    assert smtp_to == ['bea@kaupamex.mx']


def test_prepare_refuses_a_message_without_recipients():
    msg = _model()._build_email__('ana@kaupamex.mx', [], 'Hola', 'Cuerpo')
    with pytest.raises(AssertionError, match='valid recipient'):
        _model()._prepare_email_message__(msg, None)
