"""DEC-12 — sesión reautenticada para acciones sensibles.

Verifica el shape A de :ref:`analisis-diseno-reauth-sensibles-dec12`:

- endpoint ``/api/v2/authz/reauth/`` (GET estado / POST abrir / DELETE cerrar);
- el gate en ``HasCapability``: una **mutación sensible** (``PATCH`` de settings,
  ``settings.edit``) sin sesión reautenticada fresca devuelve **403
  REAUTH_REQUIRED**; tras re-autenticar, la misma mutación pasa;
- **leer** datos sensibles NO exige re-auth;
- el **superadmin NO está exento** (no es elevación de privilegios: confirma
  identidad, no otorga poderes);
- la ventana expira;
- resolver de disparo (``code_requires_fresh_session``) por caso.

Auth por sesión de servidor (``force_login``) — la ventana se ata al
``session_key`` de la sesión Django.
"""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from addons.authz.models import ReauthSession, Role, RoleAssignment
from addons.authz_audit.models import AuthzEvent
from addons.authz.services import (
    SUPERADMIN_ROLE_CODE,
    code_requires_fresh_session,
    has_active_reauth_session,
    is_superadmin,
)
from addons.users.models import EmployeeProfile

User = get_user_model()

REAUTH_URL = '/api/v2/authz/reauth/'
SETTINGS_URL = '/api/v2/config/settings/'
PASSWORD = 'ReauthPass123!'


@pytest.fixture
def seeded(db):
    """Catálogo authz sembrado (incluye ``settings`` sensible + rol superadmin)."""
    call_command('seed_authz')


@pytest.fixture
def superadmin(seeded):
    u = User.objects.create_user(email='reauth-admin@practicayoruba.mx', password=PASSWORD)
    EmployeeProfile.objects.create(identity=u)
    role, _ = Role.objects.get_or_create(
        code=SUPERADMIN_ROLE_CODE, defaults={'name': 'Superadministrador'})
    RoleAssignment.objects.get_or_create(user=u, role=role)
    return u


@pytest.fixture
def client(superadmin):
    """Cliente autenticado por sesión (session_key poblado, DEC-12)."""
    c = APIClient()
    c.force_login(superadmin)
    return c


# ─── endpoint /authz/reauth/ ─────────────────────────────────────────────────

@pytest.mark.django_db
def test_reauth_status_inactive_by_default(client):
    r = client.get(REAUTH_URL)
    assert r.status_code == 200
    assert r.data['active'] is False


@pytest.mark.django_db
def test_reauth_wrong_password_400(client):
    r = client.post(REAUTH_URL, {'password': 'wrong'}, format='json')
    assert r.status_code == 400
    assert r.data['codigo_error'] == 'REAUTH_INVALID_PASSWORD'
    assert AuthzEvent.objects.filter(
        action=AuthzEvent.ACTION_DENY, capability_code='authz.reauth').exists()


@pytest.mark.django_db
def test_reauth_open_then_active(client):
    r = client.post(REAUTH_URL, {'password': PASSWORD}, format='json')
    assert r.status_code == 200
    assert r.data['expires_in'] > 0
    status = client.get(REAUTH_URL)
    assert status.data['active'] is True
    assert AuthzEvent.objects.filter(
        action=AuthzEvent.ACTION_SENSITIVE_USE, capability_code='authz.reauth').exists()


@pytest.mark.django_db
def test_reauth_close(client):
    client.post(REAUTH_URL, {'password': PASSWORD}, format='json')
    r = client.delete(REAUTH_URL)
    assert r.status_code == 204
    assert client.get(REAUTH_URL).data['active'] is False


# ─── gate en HasCapability sobre una mutación sensible real ──────────────────

@pytest.mark.django_db
def test_sensitive_mutation_without_reauth_403(client):
    # PATCH settings (settings.edit, sensible) sin re-auth → 403 REAUTH_REQUIRED.
    r = client.patch(SETTINGS_URL, {'min_stock_threshold': 7}, format='json')
    assert r.status_code == 403
    assert r.data['codigo_error'] == 'REAUTH_REQUIRED'
    assert r.data['reauth_url'] == REAUTH_URL
    assert AuthzEvent.objects.filter(
        action=AuthzEvent.ACTION_DENY, capability_code='settings.edit').exists()


@pytest.mark.django_db
def test_superadmin_not_exempt(client, superadmin):
    # El actor ES superadmin (bypass de capacidad) y AUN ASI se le exige re-auth:
    # confirmar identidad no es un privilegio, es una defensa.
    assert is_superadmin(superadmin) is True
    r = client.patch(SETTINGS_URL, {'min_stock_threshold': 3}, format='json')
    assert r.status_code == 403
    assert r.data['codigo_error'] == 'REAUTH_REQUIRED'


@pytest.mark.django_db
def test_sensitive_mutation_passes_after_reauth(client):
    assert client.post(REAUTH_URL, {'password': PASSWORD}, format='json').status_code == 200
    r = client.patch(SETTINGS_URL, {'min_stock_threshold': 9}, format='json')
    assert r.status_code == 200
    assert r.data['min_stock_threshold'] == 9


@pytest.mark.django_db
def test_reading_sensitive_never_requires_reauth(client):
    # GET settings (settings.edit pero método seguro) NO exige re-auth.
    r = client.get(SETTINGS_URL)
    assert r.status_code == 200


@pytest.mark.django_db
def test_expired_window_re_triggers(client, superadmin):
    client.post(REAUTH_URL, {'password': PASSWORD}, format='json')
    # Envejecer la ventana: expira en el pasado.
    ReauthSession.objects.filter(user=superadmin).update(
        expires_at=timezone.now() - timedelta(seconds=1))
    r = client.patch(SETTINGS_URL, {'min_stock_threshold': 4}, format='json')
    assert r.status_code == 403
    assert r.data['codigo_error'] == 'REAUTH_REQUIRED'


# ─── regresión: mutación NO sensible nunca pide re-auth (resolver) ───────────

@pytest.mark.django_db
def test_code_requires_fresh_session_matrix(seeded):
    # Sustantivo sensible + mutación → True.
    assert code_requires_fresh_session('settings.edit', unsafe_method=True) is True
    assert code_requires_fresh_session('payments.edit', unsafe_method=True) is True
    # Sustantivo sensible pero lectura → False (no fricción para ver).
    assert code_requires_fresh_session('payments.view', unsafe_method=False) is False
    assert code_requires_fresh_session('payments.edit', unsafe_method=False) is False
    # Sustantivo NO sensible + mutación → False.
    assert code_requires_fresh_session('catalogue.edit', unsafe_method=True) is False
    # Acción nombrada sensible → True (intrínsecamente mutante).
    assert code_requires_fresh_session('platform.provision', unsafe_method=True) is True
    assert code_requires_fresh_session('inventory.adjust', unsafe_method=True) is True
    # Acción nombrada NO sensible → False.
    assert code_requires_fresh_session('reports.export', unsafe_method=True) is False
    # Sin código → False.
    assert code_requires_fresh_session('', unsafe_method=True) is False


@pytest.mark.django_db
def test_has_active_reauth_session_expiry(superadmin):
    now = timezone.now()
    ReauthSession.objects.create(
        user=superadmin, session_key='k', started_at=now,
        expires_at=now + timedelta(seconds=60))
    assert has_active_reauth_session(superadmin, 'k') is True
    ReauthSession.objects.filter(user=superadmin).update(
        expires_at=now - timedelta(seconds=1))
    assert has_active_reauth_session(superadmin, 'k') is False
