"""Integration — menú de cuenta dinámico del comprador (DEC-AUTHZ-BUYER).

El menú de "Mi cuenta" pasa de una lista estática en el UI a ser
registro-dirigido: se siembra como ``MenuItem`` con ``audience='account'`` y se
sirve por ``GET /api/v2/authz/me/menu/?audience=account``, podado por las
capacidades ``account.*`` del rol ``comprador`` (asignado al registrarse). El
menú admin (``audience='admin'``, default) NO debe incluir ítems de cuenta y
viceversa. Agregar un menú futuro = sembrar una fila, sin tocar el UI.
"""
from addons.authz.models import MenuItem, Role, RoleAssignment
from addons.authz.services import (
    BUYER_ROLE_CODE, SUPERADMIN_ROLE_CODE, assign_buyer_role,
    invalidate_capabilities,
)

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

pytestmark = pytest.mark.integration

User = get_user_model()

MENU_URL = '/api/v2/authz/me/menu/'
ACCOUNT_URL = f'{MENU_URL}?audience=account'


@pytest.fixture
def seeded(db):
    call_command('seed_authz')
    call_command('seed_menu')


@pytest.fixture
def client():
    return APIClient()


def _user(email):
    return User.objects.create_user(email=email, password='x')


def _labels(nodes):
    """Aplana labels de un árbol de menú (secciones + hojas)."""
    out = []
    for n in nodes:
        out.append(n['label'])
        out.extend(_labels(n.get('children', [])))
    return out


# ── Seed ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_seed_creates_buyer_role_with_account_caps(seeded):
    role = Role.objects.get(code=BUYER_ROLE_CODE)
    caps = set(role.capabilities.values_list('code', flat=True))
    assert 'account.orders' in caps
    assert 'account.profile' in caps
    # El rol comprador NO agrupa capacidades admin.
    assert not any(not c.startswith('account.') for c in caps)


@pytest.mark.django_db
def test_seed_marks_account_menu_audience(seeded):
    assert MenuItem.objects.filter(
        audience='account', key='cuenta-pedidos').exists()
    # Los ítems admin conservan audience='admin'.
    assert MenuItem.objects.filter(
        audience='admin', key='pedidos').exists()


# ── /me/menu/?audience=account ───────────────────────────────────────────────

@pytest.mark.django_db
def test_account_menu_requires_auth(seeded, client):
    assert client.get(ACCOUNT_URL).status_code == 401


@pytest.mark.django_db
def test_buyer_sees_account_menu(seeded, client):
    u = _user('buyer@e.com')
    assign_buyer_role(u)
    client.force_authenticate(u)

    resp = client.get(ACCOUNT_URL)
    assert resp.status_code == 200
    labels = _labels(resp.json())
    assert 'Mi cuenta' in labels          # sección
    assert 'Mis pedidos' in labels        # hoja gated por account.orders
    assert 'Mi perfil' in labels


@pytest.mark.django_db
def test_account_menu_empty_without_buyer_role(seeded, client):
    # Un usuario autenticado SIN el rol comprador no ve el menú de cuenta
    # (la sección se poda por no tener hijos visibles). No hay negación en UI.
    u = _user('norole@e.com')
    client.force_authenticate(u)
    resp = client.get(ACCOUNT_URL)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.django_db
def test_buyer_gets_empty_admin_menu(seeded, client):
    # El comprador pidiendo el menú admin (default) recibe []: no tiene
    # capacidades admin, y el filtro por audiencia lo aísla.
    u = _user('buyer2@e.com')
    assign_buyer_role(u)
    client.force_authenticate(u)
    resp = client.get(MENU_URL)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.django_db
def test_admin_menu_excludes_account_section(seeded, client):
    # Un superadmin ve TODO el menú admin, pero 'Mi cuenta' (audience=account)
    # NO aparece mezclado en el menú admin.
    boss = _user('boss@e.com')
    RoleAssignment.objects.create(
        user=boss, role=Role.objects.get(code=SUPERADMIN_ROLE_CODE))
    invalidate_capabilities(boss.id)
    client.force_authenticate(boss)
    resp = client.get(MENU_URL)
    assert resp.status_code == 200
    assert 'Mi cuenta' not in _labels(resp.json())
    # ...y el superadmin sí puede pedir su propio menú de cuenta.
    acc = client.get(ACCOUNT_URL)
    assert 'Mi cuenta' in _labels(acc.json())


# ── assign_buyer_role ────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_assign_buyer_role_idempotent(seeded):
    u = _user('idem@e.com')
    assert assign_buyer_role(u) is True
    assert assign_buyer_role(u) is True  # segunda vez no duplica
    assert RoleAssignment.objects.filter(
        user=u, role__code=BUYER_ROLE_CODE).count() == 1


@pytest.mark.django_db
def test_assign_buyer_role_tolerant_without_seed(db):
    # Sin seed_authz el rol no existe: no rompe, devuelve False.
    u = _user('noseed@e.com')
    assert assign_buyer_role(u) is False
