"""Integration — editor de permisos por rol (UC-ADM-02, H-UI-PERM-01).

La UI ``/admin/permissions`` (``AdminPermissionsPage``) es una matriz
roles×capacidades: consume ``GET /api/v2/admin/permissions/`` para pintarla y
``PUT /api/v2/admin/roles/<code>/permissions/`` para guardar el set de cada
rol. Hasta ahora esos dos endpoints no existían en la API (solo mocks MSW en la
UI) — los roles eran estáticos por seed. Este módulo los implementa con
contención de escalada: un delegado con ``permissions.manage`` solo puede
togglear capacidades que él mismo posee; el superadmin no tiene ese límite y su
rol solo lo edita otro superadmin.
"""
from apps.authz.models import Capability, Role, RoleAssignment
from apps.authz.services import (
    SUPERADMIN_ROLE_CODE, invalidate_capabilities, resolve_capabilities,
)

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

pytestmark = pytest.mark.integration

User = get_user_model()

CATALOG_URL = '/api/v2/admin/permissions/'


def _role_url(code):
    return f'/api/v2/admin/roles/{code}/permissions/'


@pytest.fixture
def seeded(db):
    call_command('seed_authz')


@pytest.fixture
def client():
    return APIClient()


def _user(email):
    return User.objects.create_user(email=email, password='x')


def _role_with(codes, code='r', name='Rol'):
    role = Role.objects.create(code=code, name=name)
    role.capabilities.set(Capability.objects.filter(code__in=codes))
    return role


def _manager(client, caps=('permissions.manage', 'users.view')):
    u = _user('mgr@e.com')
    RoleAssignment.objects.create(user=u, role=_role_with(caps, code='mgr-role'))
    invalidate_capabilities(u.id)
    client.force_authenticate(u)
    return u


def _superadmin(client):
    u = _user('boss@e.com')
    RoleAssignment.objects.create(
        user=u, role=Role.objects.get(code=SUPERADMIN_ROLE_CODE))
    invalidate_capabilities(u.id)
    client.force_authenticate(u)
    return u


# ─────────────────────────── GET /admin/permissions/ ───────────────────────

@pytest.mark.django_db
def test_catalog_requires_auth(seeded, client):
    assert client.get(CATALOG_URL).status_code == 401


@pytest.mark.django_db
def test_catalog_forbidden_without_permissions_manage(seeded, client):
    u = _user('sup@e.com')
    RoleAssignment.objects.create(user=u, role=_role_with(['support.manage']))
    invalidate_capabilities(u.id)
    client.force_authenticate(u)
    assert client.get(CATALOG_URL).status_code == 403


@pytest.mark.django_db
def test_catalog_shape_for_manager(seeded, client):
    _manager(client)
    _role_with(['users.view'], code='viewer', name='Visor')

    resp = client.get(CATALOG_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {'roles', 'permissions'}

    # roles: lista de {role, permissions}; superadmin oculto para el delegado.
    role_codes = {r['role'] for r in body['roles']}
    assert 'viewer' in role_codes
    assert SUPERADMIN_ROLE_CODE not in role_codes
    viewer = next(r for r in body['roles'] if r['role'] == 'viewer')
    assert viewer['permissions'] == ['users.view']

    # permissions (grantables): solo las capacidades propias del delegado.
    assert set(body['permissions']) == {'permissions.manage', 'users.view'}


@pytest.mark.django_db
def test_catalog_superadmin_sees_all(seeded, client):
    _superadmin(client)
    resp = client.get(CATALOG_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert SUPERADMIN_ROLE_CODE in {r['role'] for r in body['roles']}
    # El catálogo de grantables = todas las capacidades activas.
    all_active = set(
        Capability.objects.filter(is_active=True).values_list('code', flat=True))
    assert set(body['permissions']) == all_active
    assert body['permissions'] == sorted(body['permissions'])


# ──────────────────── PUT /admin/roles/<code>/permissions/ ──────────────────

@pytest.mark.django_db
def test_put_requires_auth(seeded, client):
    _role_with([], code='r')
    assert client.put(_role_url('r'), {'permissions': []},
                      format='json').status_code == 401


@pytest.mark.django_db
def test_put_forbidden_without_permissions_manage(seeded, client):
    u = _user('sup@e.com')
    RoleAssignment.objects.create(user=u, role=_role_with(['support.manage']))
    invalidate_capabilities(u.id)
    client.force_authenticate(u)
    _role_with([], code='target')
    assert client.put(_role_url('target'), {'permissions': []},
                      format='json').status_code == 403


@pytest.mark.django_db
def test_put_role_not_found(seeded, client):
    _manager(client)
    resp = client.put(_role_url('does-not-exist'), {'permissions': []},
                      format='json')
    assert resp.status_code == 404
    assert resp.json()['codigo_error'] == 'ROLE_NOT_FOUND'


@pytest.mark.django_db
def test_put_manager_cannot_edit_superadmin_role(seeded, client):
    _manager(client)
    resp = client.put(_role_url(SUPERADMIN_ROLE_CODE),
                      {'permissions': ['users.view']}, format='json')
    assert resp.status_code == 403
    assert resp.json()['codigo_error'] == 'CANNOT_EDIT_SUPERADMIN'


@pytest.mark.django_db
def test_put_unknown_capability_400(seeded, client):
    _manager(client)
    _role_with([], code='target')
    resp = client.put(_role_url('target'),
                      {'permissions': ['no.existe']}, format='json')
    assert resp.status_code == 400
    assert resp.json()['codigo_error'] == 'UNKNOWN_CAPABILITY'


@pytest.mark.django_db
def test_put_manager_cannot_grant_unheld_capability(seeded, client):
    # El delegado tiene {permissions.manage, users.view}; intenta conceder al
    # rol 'target' la capacidad 'support.manage' que él NO posee → escalada.
    _manager(client)
    _role_with([], code='target')
    resp = client.put(_role_url('target'),
                      {'permissions': ['support.manage']}, format='json')
    assert resp.status_code == 403
    assert resp.json()['codigo_error'] == 'CANNOT_GRANT_UNHELD_CAPABILITY'
    # No se materializó el cambio.
    assert set(Role.objects.get(code='target')
               .capabilities.values_list('code', flat=True)) == set()


@pytest.mark.django_db
def test_put_manager_grants_held_capability(seeded, client):
    _manager(client)
    _role_with([], code='target')
    resp = client.put(_role_url('target'),
                      {'permissions': ['users.view']}, format='json')
    assert resp.status_code == 200
    assert resp.json() == {'role': 'target', 'permissions': ['users.view']}
    assert set(Role.objects.get(code='target')
               .capabilities.values_list('code', flat=True)) == {'users.view'}


@pytest.mark.django_db
def test_put_preserves_frozen_capabilities(seeded, client):
    # 'target' ya tiene 'support.manage' (que el delegado NO posee). El delegado
    # agrega 'users.view' (que sí posee) SIN tocar la congelada → OK, y la
    # congelada se preserva.
    _manager(client)
    _role_with(['support.manage'], code='target')
    resp = client.put(
        _role_url('target'),
        {'permissions': ['support.manage', 'users.view']}, format='json')
    assert resp.status_code == 200
    assert set(Role.objects.get(code='target')
               .capabilities.values_list('code', flat=True)) == {
        'support.manage', 'users.view'}


@pytest.mark.django_db
def test_put_manager_cannot_revoke_frozen_capability(seeded, client):
    # Quitar 'support.manage' (que el delegado no posee) es también escalada
    # (neutralizar una capacidad que no controla).
    _manager(client)
    _role_with(['support.manage'], code='target')
    resp = client.put(_role_url('target'), {'permissions': []}, format='json')
    assert resp.status_code == 403
    assert resp.json()['codigo_error'] == 'CANNOT_GRANT_UNHELD_CAPABILITY'
    assert set(Role.objects.get(code='target')
               .capabilities.values_list('code', flat=True)) == {'support.manage'}


@pytest.mark.django_db
def test_put_superadmin_sets_any_capabilities(seeded, client):
    _superadmin(client)
    _role_with([], code='target')
    resp = client.put(
        _role_url('target'),
        {'permissions': ['support.manage', 'users.view']}, format='json')
    assert resp.status_code == 200
    assert set(resp.json()['permissions']) == {'support.manage', 'users.view'}


@pytest.mark.django_db
def test_put_invalidates_assignee_capability_cache(seeded, client):
    # Un usuario tiene el rol 'target'; al mutar el rol, su set efectivo cambia.
    _superadmin(client)
    role = _role_with(['users.view'], code='target')
    assignee = _user('assignee@e.com')
    RoleAssignment.objects.create(user=assignee, role=role)
    # Poblar la cache del assignee con el estado viejo.
    assert 'users.view' in resolve_capabilities(assignee)

    resp = client.put(
        _role_url('target'),
        {'permissions': ['users.view', 'support.manage']}, format='json')
    assert resp.status_code == 200
    # Sin invalidación, resolve_capabilities devolvería el set cacheado viejo.
    assert 'support.manage' in resolve_capabilities(assignee)
