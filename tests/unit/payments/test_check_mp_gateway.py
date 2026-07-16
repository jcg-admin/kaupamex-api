"""
Tests del management command check_mp_gateway (V-MP).

Verifican que el diagnóstico:
  - falle (exit 1) si no hay gateway / falta access_token / falta public_key,
  - pase (exit 0) en Sandbox y en Producción con creds completas,
  - trate client_secret ausente como advertencia (no bloqueo),
  - NUNCA imprima el valor completo de un token (solo ****+últimos 4),
  - con --ping consulte el SDK y falle si el token no autentica.

BD: practicayoruba_qa (config.settings.testing).
"""
import json

import pytest
from django.core.management import call_command

from apps.addons.settings_app.models import PaymentGateway

pytestmark = pytest.mark.unit

# Tokens de prueba (ficticios) — sirven para verificar el enmascarado.
_SANDBOX_TOKEN = 'TEST-1234567890-abcdefRAW'
_PROD_TOKEN    = 'APP_USR-1234567890-abcdefRAW'
_PUBLIC_KEY    = 'APP_USR-pk-0000-1111-LAST'
_CLIENT_SECRET = 'whsec-supersecretVALUE'


def _make_gateway(creds, is_active=True):
    gw = PaymentGateway.objects.create(
        gateway='MERCADOPAGO', name='MercadoPago', is_active=is_active,
    )
    gw.set_credentials(creds)
    gw.save()
    return gw


class TestCheckMpGatewayExitCodes:
    def test_no_gateway_fails(self, db, capsys):
        with pytest.raises(SystemExit) as exc:
            call_command('check_mp_gateway')
        assert exc.value.code == 1
        assert 'no existe' in capsys.readouterr().err.lower()

    def test_sandbox_full_creds_ok(self, db, capsys):
        _make_gateway({
            'access_token': _SANDBOX_TOKEN,
            'public_key': _PUBLIC_KEY,
            'client_secret': _CLIENT_SECRET,
        })
        call_command('check_mp_gateway')  # no SystemExit → exit 0
        out = capsys.readouterr().out
        assert 'Sandbox' in out
        assert 'listo para cobrar' in out.lower()

    def test_prod_mode_detected(self, db, capsys):
        _make_gateway({
            'access_token': _PROD_TOKEN,
            'public_key': _PUBLIC_KEY,
        })
        call_command('check_mp_gateway')
        assert 'Producción' in capsys.readouterr().out

    def test_missing_access_token_blocks(self, db, capsys):
        _make_gateway({'public_key': _PUBLIC_KEY})
        with pytest.raises(SystemExit) as exc:
            call_command('check_mp_gateway')
        assert exc.value.code == 1
        assert 'access_token' in capsys.readouterr().err

    def test_missing_public_key_blocks(self, db, capsys):
        _make_gateway({'access_token': _SANDBOX_TOKEN})
        with pytest.raises(SystemExit) as exc:
            call_command('check_mp_gateway')
        assert exc.value.code == 1
        assert 'public_key' in capsys.readouterr().err

    def test_missing_client_secret_is_warning_not_block(self, db, capsys):
        _make_gateway({
            'access_token': _SANDBOX_TOKEN,
            'public_key': _PUBLIC_KEY,
        })
        call_command('check_mp_gateway')  # no SystemExit
        captured = capsys.readouterr()
        assert 'listo para cobrar' in captured.out.lower()
        assert 'client_secret' in captured.err

    def test_inactive_gateway_blocks(self, db, capsys):
        _make_gateway({
            'access_token': _SANDBOX_TOKEN,
            'public_key': _PUBLIC_KEY,
        }, is_active=False)
        with pytest.raises(SystemExit) as exc:
            call_command('check_mp_gateway')
        assert exc.value.code == 1


class TestCheckMpGatewayNeverLeaksSecrets:
    def test_raw_token_never_in_output(self, db, capsys):
        _make_gateway({
            'access_token': _SANDBOX_TOKEN,
            'public_key': _PUBLIC_KEY,
            'client_secret': _CLIENT_SECRET,
        })
        call_command('check_mp_gateway')
        captured = capsys.readouterr()
        blob = captured.out + captured.err
        # Ningún valor completo del token/secret aparece; sí sus últimos 4.
        assert _SANDBOX_TOKEN not in blob
        assert _CLIENT_SECRET not in blob
        assert _PUBLIC_KEY not in blob
        assert '****' + _SANDBOX_TOKEN[-4:] in blob  # ****dRAW


class _FakeMethods:
    def __init__(self, status):
        self._status = status

    def list_all(self):
        return {'status': self._status, 'response': []}


class _FakeSDK:
    def __init__(self, status):
        self._status = status

    def __call__(self, access_token):  # mimic mercadopago.SDK(token)
        return self

    def payment_methods(self):
        return _FakeMethods(self._status)


class TestCheckMpGatewayPing:
    def test_ping_ok_passes(self, db, capsys, monkeypatch):
        _make_gateway({
            'access_token': _SANDBOX_TOKEN,
            'public_key': _PUBLIC_KEY,
        })
        fake = _FakeSDK(200)
        monkeypatch.setattr('mercadopago.SDK', lambda token: fake)
        call_command('check_mp_gateway', '--ping')
        out = capsys.readouterr().out
        assert 'ping status:' in out
        assert 'ping OK' in out

    def test_ping_unauthorized_blocks(self, db, capsys, monkeypatch):
        _make_gateway({
            'access_token': _SANDBOX_TOKEN,
            'public_key': _PUBLIC_KEY,
        })
        fake = _FakeSDK(401)
        monkeypatch.setattr('mercadopago.SDK', lambda token: fake)
        with pytest.raises(SystemExit) as exc:
            call_command('check_mp_gateway', '--ping')
        assert exc.value.code == 1
        assert 'ping falló' in capsys.readouterr().err


class _FakeHTTPResponse:
    def __init__(self, body):
        self._body = body

    def read(self):
        return json.dumps(self._body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakePayment:
    def __init__(self, resp):
        self._resp = resp

    def create(self, data):
        return self._resp


class _FakeSDKPayment:
    def __init__(self, resp):
        self._resp = resp

    def payment(self):
        return _FakePayment(self._resp)


def _patch_pairing(monkeypatch, payment_resp, token_body=None):
    """Mockea la tokenización (urlopen) y el cobro (SDK.payment().create)."""
    token_body = token_body if token_body is not None else {
        'id': 'card_tok_fake', 'status': 'active'}
    monkeypatch.setattr(
        'urllib.request.urlopen',
        lambda req, timeout=None: _FakeHTTPResponse(token_body))
    monkeypatch.setattr(
        'mercadopago.SDK', lambda token: _FakeSDKPayment(payment_resp))


class TestCheckMpGatewayVerifyPairing:
    def test_pairing_mismatch_blocks(self, db, capsys, monkeypatch):
        # public_key crea token, pero el access_token es de otra app → 2006.
        _make_gateway({
            'access_token': _SANDBOX_TOKEN,
            'public_key': _PUBLIC_KEY,
        })
        _patch_pairing(monkeypatch, {
            'status': 400,
            'response': {
                'message': 'Card Token not found',
                'cause': [{'code': 2006, 'description': 'Card Token not found'}],
            },
        })
        with pytest.raises(SystemExit) as exc:
            call_command('check_mp_gateway', '--verify-pairing')
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert 'aplicaciones MP distintas' in captured.err
        assert '2006' in (captured.out + captured.err)

    def test_pairing_match_passes(self, db, capsys, monkeypatch):
        # El access_token SÍ encuentra el token (pago creado, aun rechazado).
        _make_gateway({
            'access_token': _SANDBOX_TOKEN,
            'public_key': _PUBLIC_KEY,
        })
        _patch_pairing(monkeypatch, {
            'status': 201,
            'response': {'status': 'rejected', 'id': 999},
        })
        call_command('check_mp_gateway', '--verify-pairing')  # no SystemExit
        out = capsys.readouterr().out
        assert 'pairing OK' in out
        assert 'listo para cobrar' in out.lower()

    def test_pairing_public_key_cannot_tokenize_blocks(
            self, db, capsys, monkeypatch):
        # public_key no devuelve token → no se puede emparejar.
        _make_gateway({
            'access_token': _SANDBOX_TOKEN,
            'public_key': _PUBLIC_KEY,
        })
        _patch_pairing(monkeypatch, {'status': 201, 'response': {}},
                       token_body={'status': 'error'})
        with pytest.raises(SystemExit) as exc:
            call_command('check_mp_gateway', '--verify-pairing')
        assert exc.value.code == 1
