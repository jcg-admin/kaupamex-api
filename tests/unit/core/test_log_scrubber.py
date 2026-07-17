"""Tests unitarios — PIIScrubber (SOL-011 T-02, DEC-LOG-03 Nivel 1).

Verifican que ``scrub`` redacta secretos de Nivel 1 (password, token,
Authorization, cvv, pan, ...) en texto libre (msg / error_detail / trace),
en cualquier forma (``key=value``, JSON, dict-repr, header Bearer, PAN),
sin tocar metadata de Nivel 3 (username, path, status). Funcion pura: no
toca DB → no requiere django_db.
"""
import pytest

from core.log_scrubber import REDACTED, scrub

pytestmark = [pytest.mark.unit]


@pytest.mark.parametrize('raw', [
    "password=hunter2",
    "passwd=hunter2",
    "pwd: hunter2",
    'password = "hunter2"',
    "{'password': 'hunter2'}",
    '{"password": "hunter2"}',
])
def test_redacts_password_forms(raw):
    out = scrub(raw)
    assert 'hunter2' not in out
    assert REDACTED in out


@pytest.mark.parametrize('key', [
    'token', 'access_token', 'refresh_token', 'card_token',
    'secret', 'client_secret', 'api_key', 'apikey', 'cvv', 'cvc', 'pan',
])
def test_redacts_each_secret_key(key):
    out = scrub(f'{key}=SUPERSECRETVALUE1')
    assert 'SUPERSECRETVALUE1' not in out
    assert REDACTED in out


def test_redacts_json_quoted_value_keeps_quotes():
    out = scrub('{"access_token": "eyJhbGciOi"}')
    assert 'eyJhbGciOi' not in out
    assert f'"{REDACTED}"' in out


def test_redacts_authorization_bearer_header():
    out = scrub('Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig')
    assert 'eyJhbGciOiJIUzI1NiJ9.payload.sig' not in out
    assert REDACTED in out


def test_redacts_bare_bearer_token():
    out = scrub('sent header Bearer abc123def456ghi789 to gateway')
    assert 'abc123def456ghi789' not in out
    assert REDACTED in out


def test_redacts_pan_16_digits():
    out = scrub('card number 4111111111111111 declined')
    assert '4111111111111111' not in out
    assert REDACTED in out


def test_redacts_pan_grouped():
    out = scrub('PAN 4111 1111 1111 1111 flagged')
    assert '4111 1111 1111 1111' not in out
    assert REDACTED in out


def test_case_insensitive_keys():
    out = scrub('Password=hunter2 and TOKEN=abcXYZ123456')
    assert 'hunter2' not in out
    assert 'abcXYZ123456' not in out


def test_redacts_inside_traceback():
    trace = (
        'Traceback (most recent call last):\n'
        '  File "views.py", line 42, in post\n'
        "    charge(card_token='tok_live_51H', password='hunter2')\n"
        'ValueError: boom\n'
    )
    out = scrub(trace)
    assert 'tok_live_51H' not in out
    assert 'hunter2' not in out
    # el resto del traceback (no secreto) se conserva
    assert 'Traceback' in out
    assert 'ValueError: boom' in out


@pytest.mark.parametrize('safe', [
    'username=bob',
    'user_id=42',
    'path=/api/v2/catalogue/products/',
    'status_code=500 duration_ms=1234',
    'method=POST view_name=admin_logs',
    'correlation_id=deadbeef',
])
def test_does_not_touch_non_secret_metadata(safe):
    assert scrub(safe) == safe


def test_none_and_empty_pass_through():
    assert scrub(None) is None
    assert scrub('') == ''


def test_idempotent():
    raw = "password=hunter2 token=abc123456789 pan=4111111111111111"
    once = scrub(raw)
    assert scrub(once) == once


def test_non_string_coerced():
    out = scrub({'password': 'hunter2'})
    assert 'hunter2' not in out
    assert REDACTED in out
