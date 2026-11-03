"""``hmac`` — ≙ ``odoo19c: odoo/tools/misc.py`` (``def hmac``).

La clave es el parámetro ``database.secret`` y lo firmado es
``repr((scope, message))``, con SHA-256 por defecto. La firma lleva ``env``
como primer argumento, que es la forma en que la llaman los addons portados
(``addons/website/tools.py``).
"""

import base64
import datetime
import hashlib
import hmac as hmac_lib

import pytest
from lxml import html

from addons.website.tools import add_form_signature
from orm.environments import Environment
from orm.utils import SUPERUSER_ID
from tools.misc import (hash_sign, hmac, limited_field_access_token,
                        verify_hash_signed, verify_limited_field_access_token)

pytestmark = pytest.mark.django_db


def _env():
    return Environment(None, SUPERUSER_ID, {})


def test_signs_the_scope_and_message_with_the_database_secret():
    with _env() as env:
        secret = env['ir.config_parameter'].get_param('database.secret')
        expected = hmac_lib.new(secret.encode(), repr(('s', 'm')).encode(),
                                hashlib.sha256).hexdigest()
        assert hmac(env, 's', 'm') == expected


def test_the_scope_changes_the_signature():
    with _env() as env:
        assert hmac(env, 'a', 'm') != hmac(env, 'b', 'm')


def test_an_empty_scope_is_refused():
    with _env() as env, pytest.raises(ValueError, match='Non-empty scope required'):
        hmac(env, '', 'm')


def test_the_website_form_signature_signs_the_recipient():
    """El consumidor que llama con la forma de la fuente
    (``addons/website/tools.py``, ``add_form_signature``). Con la firma
    anterior de ``hmac`` este caso moría con ``InvalidAlgorithm``."""
    fragment = html.fromstring(
        '<div><form action="/website/form/mail.mail">'
        '<input name="email_to" value="a@b.mx"/>'
        '<input name="email_cc" value=""/></form></div>')
    with _env() as env:
        add_form_signature(fragment, env)
        signature = fragment.xpath('//input[@name="website_form_signature"]')[0]
        assert signature.attrib['value'] == (
            hmac(env, 'website_form_signature', 'a@b.mx:email_cc') + ':email_cc')


class TestHashSign:
    """≙ ``hash_sign`` / ``verify_hash_signed`` (``odoo19c:
    odoo/tools/misc.py:1802-1851``)."""

    def test_round_trip(self):
        with _env() as env:
            token = hash_sign(env, 'scope', {'a': [1, 2]})
            assert verify_hash_signed(env, 'scope', token) == {'a': [1, 2]}

    def test_another_scope_does_not_verify(self):
        with _env() as env:
            token = hash_sign(env, 'scope', [1])
            assert verify_hash_signed(env, 'other', token) is None

    def test_an_expired_token_does_not_verify(self):
        with _env() as env:
            token = hash_sign(env, 'scope', [1], expiration=datetime.timedelta(seconds=-1))
            assert verify_hash_signed(env, 'scope', token) is None

    def test_an_unknown_version_is_refused(self):
        with _env() as env:
            bad = base64.urlsafe_b64encode(b'\x02' + b'\x00' * 40).decode()
            with pytest.raises(ValueError, match='Unknown token version'):
                verify_hash_signed(env, 'scope', bad)


def test_limited_field_access_token_round_trip(env_orm_record):
    record = env_orm_record
    token = limited_field_access_token(record, 'name', scope='download')
    assert verify_limited_field_access_token(record, 'name', token, scope='download')
    assert not verify_limited_field_access_token(record, 'name', token, scope='other')
    assert not verify_limited_field_access_token(record, 'text', token, scope='download')
    expired = limited_field_access_token(record, 'name', hex(1), scope='download')
    assert not verify_limited_field_access_token(record, 'name', expired, scope='download')


@pytest.fixture
def env_orm_record():
    with _env() as env:
        yield env['test_orm.foo'].create({'name': 'x'})
