"""authz_totp — códigos de recuperación (DEC-01, ~recovery codes de auth_totp).

Cubre: generación al activar el 2FA, login con un código de recuperación
(un solo uso), regeneración, desactivación con un código de recuperación, y el
conteo restante en el status. Se guardan hasheados (el plano se muestra una vez).
"""
import base64
import time

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

from addons.authz.services import assign_buyer_role, invalidate_capabilities
from addons.auth_totp.models import TotpRecoveryCode, TotpSecret
from addons.auth_totp.services import (
    count_recovery_codes,
    generate_recovery_codes,
    generate_secret,
)
from addons.auth_totp.totp import hotp

pytestmark = pytest.mark.django_db

User = get_user_model()
LOGIN_URL = '/api/v2/auth/login/'
STATUS_URL = '/api/v2/authz/totp/'
SETUP_URL = '/api/v2/authz/totp/setup/'
CONFIRM_URL = '/api/v2/authz/totp/confirm/'
DISABLE_URL = '/api/v2/authz/totp/disable/'
RECOVERY_URL = '/api/v2/authz/totp/recovery-codes/'

PASSWORD = 'Str0ng-Passw0rd!'


def _current_code(secret, offset=0):
    key = base64.b32decode(secret)
    counter = int(time.time() // 30) + offset
    return f'{hotp(key, counter):06d}'


@pytest.fixture
def user(db):
    # 2FA gateado por ``account.security`` (cuenta propia); el rol comprador la
    # agrupa. Ver test_totp.py.
    call_command('seed_authz')
    u = User.objects.create_user(
        login='recovery-user@example.com', password=PASSWORD, is_active=True,
    )
    assign_buyer_role(u)
    invalidate_capabilities(u.id)
    return u


@pytest.fixture
def auth_client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# --- generación al activar ---------------------------------------------------

def test_confirm_returns_recovery_codes(auth_client, user):
    secret = auth_client.post(SETUP_URL).data['secret']
    confirm = auth_client.post(CONFIRM_URL, {'code': _current_code(secret)}, format='json')
    assert confirm.status_code == 200
    codes = confirm.data['recovery_codes']
    assert len(codes) == 10                                   # default Odoo
    assert count_recovery_codes(user) == 10
    # Se guardan hasheados, nunca el plano.
    stored = TotpRecoveryCode.objects.filter(user=user).values_list('code_hash', flat=True)
    assert codes[0] not in stored


def test_status_reports_remaining(auth_client, user):
    secret = generate_secret()
    TotpSecret.objects.create(user=user, secret=secret, confirmed=True)
    generate_recovery_codes(user)
    data = auth_client.get(STATUS_URL).data
    assert data['enabled'] is True and data['recovery_codes_remaining'] == 10


# --- login con código de recuperación (un solo uso) --------------------------

def test_login_with_recovery_code_consumes_it(user):
    secret = generate_secret()
    TotpSecret.objects.create(user=user, secret=secret, confirmed=True)
    codes = generate_recovery_codes(user)
    code = codes[0]
    # login con el código de recuperación como 'otp' -> 200
    r1 = APIClient().post(
        LOGIN_URL, {'email': user.email, 'password': PASSWORD, 'otp': code}, format='json',
    )
    assert r1.status_code == 200 and 'access' in r1.data
    assert count_recovery_codes(user) == 9                    # consumido
    # el mismo código NO vuelve a servir -> 401
    r2 = APIClient().post(
        LOGIN_URL, {'email': user.email, 'password': PASSWORD, 'otp': code}, format='json',
    )
    assert r2.status_code == 401 and r2.data['codigo_error'] == 'TOTP_INVALID'


def test_login_with_totp_still_works_alongside_recovery(user):
    secret = generate_secret()
    TotpSecret.objects.create(user=user, secret=secret, confirmed=True)
    generate_recovery_codes(user)
    r = APIClient().post(
        LOGIN_URL,
        {'email': user.email, 'password': PASSWORD, 'otp': _current_code(secret)},
        format='json',
    )
    assert r.status_code == 200 and 'access' in r.data
    assert count_recovery_codes(user) == 10                   # TOTP no consume backup


# --- regeneración ------------------------------------------------------------

def test_regenerate_replaces_old_codes(auth_client, user):
    secret = generate_secret()
    TotpSecret.objects.create(user=user, secret=secret, confirmed=True)
    old = generate_recovery_codes(user)
    resp = auth_client.post(RECOVERY_URL, {'code': _current_code(secret)}, format='json')
    assert resp.status_code == 200
    new = resp.data['recovery_codes']
    assert set(new).isdisjoint(old)                           # nuevos != viejos
    # un código viejo ya no inicia sesión
    r = APIClient().post(
        LOGIN_URL, {'email': user.email, 'password': PASSWORD, 'otp': old[0]}, format='json',
    )
    assert r.status_code == 401


def test_regenerate_requires_valid_totp(auth_client, user):
    secret = generate_secret()
    TotpSecret.objects.create(user=user, secret=secret, confirmed=True)
    generate_recovery_codes(user)
    assert auth_client.post(RECOVERY_URL, {'code': '000000'}, format='json').status_code == 400


def test_regenerate_rejected_without_2fa(auth_client, user):
    resp = auth_client.post(RECOVERY_URL, {'code': '000000'}, format='json')
    assert resp.status_code == 409 and resp.data['codigo_error'] == 'TOTP_NOT_ENABLED'


# --- desactivación con código de recuperación --------------------------------

def test_disable_with_recovery_code(auth_client, user):
    secret = generate_secret()
    TotpSecret.objects.create(user=user, secret=secret, confirmed=True)
    codes = generate_recovery_codes(user)
    # el endpoint de disable acepta un código de recuperación (no sólo 6 dígitos)
    ok = auth_client.post(DISABLE_URL, {'code': codes[0]}, format='json')
    assert ok.status_code == 200 and ok.data['enabled'] is False
    assert TotpSecret.objects.filter(user=user).count() == 0
    assert TotpRecoveryCode.objects.filter(user=user).count() == 0
