"""authz_totp — 2FA por TOTP (DEC-01, ~auth_totp de Odoo).

Cubre el algoritmo (adaptado verbatim de Odoo), el flujo de alta
(setup → confirm), el gate del **login** (segundo factor tras la contraseña)
y la desactivación. El login sin 2FA no se ve afectado (sin regresión).
"""
import base64
import time

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

from addons.authz.services import assign_buyer_role, invalidate_capabilities
from addons.auth_totp.models import TotpSecret
from addons.auth_totp.services import (
    _code_matches,
    generate_secret,
    provisioning_uri,
    verify_code,
)
from addons.auth_totp.totp import hotp

pytestmark = pytest.mark.django_db

User = get_user_model()
LOGIN_URL = '/api/v2/auth/login/'
STATUS_URL = '/api/v2/authz/totp/'
SETUP_URL = '/api/v2/authz/totp/setup/'
CONFIRM_URL = '/api/v2/authz/totp/confirm/'
DISABLE_URL = '/api/v2/authz/totp/disable/'

PASSWORD = 'Str0ng-Passw0rd!'


def _current_code(secret, offset=0):
    """Código TOTP válido ahora (mismo hotp que Odoo). ``offset`` en pasos de 30s."""
    key = base64.b32decode(secret)
    counter = int(time.time() // 30) + offset
    return f'{hotp(key, counter):06d}'


@pytest.fixture
def user(db):
    # Los endpoints de 2FA están gateados por la capacidad de cuenta propia
    # ``account.security`` (CapabilityRequiredMixin). El usuario necesita un rol
    # que la tenga; el rol comprador agrupa todas las ``account.*``.
    call_command('seed_authz')
    u = User.objects.create_user(
        login='totp-user@example.com', password=PASSWORD, is_active=True,
    )
    assign_buyer_role(u)
    invalidate_capabilities(u.id)
    return u


@pytest.fixture
def auth_client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# --- algoritmo (adaptación verbatim de Odoo) --------------------------------

def test_verify_code_matches_current_and_rejects_wrong():
    secret = generate_secret()
    assert _code_matches(secret, _current_code(secret)) is True
    assert _code_matches(secret, 'abcdef') is False  # no numérico
    # un código de un paso lejano NO casa (fuera de la ventana ±30s)
    assert _code_matches(secret, _current_code(secret, offset=10)) is False


def test_provisioning_uri_shape():
    uri = provisioning_uri('a@b.com', 'JBSWY3DPEHPK3PXP')
    assert uri.startswith('otpauth://totp/')
    assert 'secret=JBSWY3DPEHPK3PXP' in uri
    assert 'algorithm=SHA1' in uri and 'digits=6' in uri and 'period=30' in uri


# --- flujo de alta ----------------------------------------------------------

def test_setup_then_confirm_enables_2fa(auth_client, user):
    assert auth_client.get(STATUS_URL).data['enabled'] is False
    setup = auth_client.post(SETUP_URL)
    assert setup.status_code == 201
    secret = setup.data['secret']
    assert setup.data['otpauth_uri'].startswith('otpauth://totp/')
    # aún no activo (pendiente de confirmar)
    assert auth_client.get(STATUS_URL).data['enabled'] is False

    confirm = auth_client.post(CONFIRM_URL, {'code': _current_code(secret)}, format='json')
    assert confirm.status_code == 200 and confirm.data['enabled'] is True
    assert auth_client.get(STATUS_URL).data['enabled'] is True


def test_confirm_wrong_code_does_not_enable(auth_client):
    auth_client.post(SETUP_URL)
    resp = auth_client.post(CONFIRM_URL, {'code': '000000'}, format='json')
    assert resp.status_code == 400
    assert auth_client.get(STATUS_URL).data['enabled'] is False


def test_setup_rejected_when_already_enabled(auth_client, user):
    secret = generate_secret()
    TotpSecret.objects.create(user=user, secret=secret, confirmed=True)
    resp = auth_client.post(SETUP_URL)
    assert resp.status_code == 409
    assert resp.data['codigo_error'] == 'TOTP_ALREADY_ENABLED'


# --- gate del login (segundo factor) ----------------------------------------

def test_login_without_2fa_unaffected(user):
    resp = APIClient().post(LOGIN_URL, {'email': user.email, 'password': PASSWORD}, format='json')
    assert resp.status_code == 200
    assert 'access' in resp.data


def test_login_with_2fa_requires_code(user):
    secret = generate_secret()
    TotpSecret.objects.create(user=user, secret=secret, confirmed=True)
    # password-only -> 401 TOTP_REQUIRED (DRF devuelve el dict detail como body)
    r1 = APIClient().post(LOGIN_URL, {'email': user.email, 'password': PASSWORD}, format='json')
    assert r1.status_code == 401
    assert r1.data['codigo_error'] == 'TOTP_REQUIRED'
    # wrong otp -> 401 TOTP_INVALID
    r2 = APIClient().post(
        LOGIN_URL, {'email': user.email, 'password': PASSWORD, 'otp': '000000'}, format='json',
    )
    assert r2.status_code == 401
    assert r2.data['codigo_error'] == 'TOTP_INVALID'
    # correct otp -> 200
    r3 = APIClient().post(
        LOGIN_URL,
        {'email': user.email, 'password': PASSWORD, 'otp': _current_code(secret)},
        format='json',
    )
    assert r3.status_code == 200 and 'access' in r3.data


# --- desactivación ----------------------------------------------------------

def test_disable_requires_valid_code(auth_client, user):
    secret = generate_secret()
    TotpSecret.objects.create(user=user, secret=secret, confirmed=True)
    assert auth_client.post(DISABLE_URL, {'code': '000000'}, format='json').status_code == 400
    ok = auth_client.post(DISABLE_URL, {'code': _current_code(secret)}, format='json')
    assert ok.status_code == 200 and ok.data['enabled'] is False
    assert not verify_code(user, _current_code(secret))
