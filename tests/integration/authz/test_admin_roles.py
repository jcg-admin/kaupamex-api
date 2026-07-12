"""Integration — GET /api/v2/admin/roles (catálogo de roles, G-PERM-01).

El formulario admin ``/admin/permissions`` (UC-ADM-02) asigna roles a un
usuario vía ``POST /api/v2/admin/users/<pk>/permissions/`` (que espera ids de
Role). Hasta ahora no existía un endpoint para **listar el catálogo completo**
de roles disponibles: el selector solo podía leer los roles ya asignados a un
usuario (``AdminUserDetailSerializer.roles``). Este endpoint cierra ese gap.

Contrato: read-only, gateado por ``permissions.manage`` (misma capacidad que
la asignación). Devuelve ``[{id, code, name, capabilities:[codes]}]``.
"""
from apps.authz.models import Capability, Role, RoleAssignment
from apps.authz.services import (
    SUPERADMIN_ROLE_CODE, invalidate_capabilities, is_superadmin,
)

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

pytestmark = pytest.mark.integration

User = get_user_model()


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


@pytest.mark.django_db
def test_requires_auth(seeded, client):
    assert client.get('/api/v2/admin/roles/').status_code == 401


@pytest.mark.django_db
def test_forbidden_without_permissions_manage(seeded, client):
    # Un usuario con otra capacidad (no permissions.manage) recibe 403.
    u = _user('sup@e.com')
    RoleAssignment.objects.create(user=u, role=_role_with(['support.manage']))
    invalidate_capabilities(u.id)
    client.force_authenticate(u)
    assert client.get('/api/v2/admin/roles/').status_code == 403


@pytest.mark.django_db
def test_lists_catalog_for_permissions_manager(seeded, client):
    u = _user('mgr@e.com')
    RoleAssignment.objects.create(user=u, role=_role_with(['permissions.manage']))
    invalidate_capabilities(u.id)
    client.force_authenticate(u)

    resp = client.get('/api/v2/admin/roles/')
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    codes = {r['code'] for r in body}
    # El rol 'r' (no privilegiado) aparece en el catálogo...
    assert 'r' in codes
    # ...pero el rol superadmin NO: un delegado con permissions.manage que no
    # es superadmin no debe poder descubrir ni asignar superadmin (contención
    # de escalada de privilegios). Ver test_manager_cannot_grant_superadmin.
    assert SUPERADMIN_ROLE_CODE not in codes

    # Contrato por item: id (para el POST de asignación), code, name, y la
    # lista de capacidades (codes) que agrupa el rol.
    r = next(item for item in body if item['code'] == 'r')
    assert set(r.keys()) == {'id', 'code', 'name', 'capabilities'}
    assert isinstance(r['id'], int)
    assert r['capabilities'] == ['permissions.manage']


@pytest.mark.django_db
def test_superadmin_sees_catalog(seeded, client):
    u = _user('boss@e.com')
    RoleAssignment.objects.create(
        user=u, role=Role.objects.get(code=SUPERADMIN_ROLE_CODE))
    invalidate_capabilities(u.id)
    client.force_authenticate(u)
    resp = client.get('/api/v2/admin/roles/')
    assert resp.status_code == 200
    codes = [r['code'] for r in resp.json()]
    # El superadmin SÍ ve el rol superadmin (solo él puede asignarlo).
    assert SUPERADMIN_ROLE_CODE in codes
    # Los items están ordenados por code (contrato estable).
    assert codes == sorted(codes)


# ── Contención de escalada de privilegios (write guard en /permissions/) ──
# El catálogo oculta superadmin al delegado, pero el candado real es en la
# escritura: un delegado no-superadmin no puede conceder ni revocar la
# membresía superadmin de NINGÚN usuario, aunque adivine el id del rol.

USERS_URL = '/api/v2/admin/users/'


@pytest.mark.django_db
def test_manager_cannot_grant_superadmin(seeded, client):
    mgr = _user('mgr@e.com')
    RoleAssignment.objects.create(
        user=mgr, role=_role_with(['permissions.manage', 'users.view']))
    invalidate_capabilities(mgr.id)
    client.force_authenticate(mgr)

    target = _user('victim@e.com')
    superadmin_id = Role.objects.get(code=SUPERADMIN_ROLE_CODE).pk
    resp = client.post(f'{USERS_URL}{target.pk}/permissions/',
                       {'roles': [superadmin_id]}, format='json')
    assert resp.status_code == 403
    assert resp.json()['codigo_error'] == 'CANNOT_GRANT_SUPERADMIN'
    # No se materializó la asignación.
    assert is_superadmin(target) is False


@pytest.mark.django_db
def test_manager_cannot_revoke_superadmin(seeded, client):
    mgr = _user('mgr@e.com')
    RoleAssignment.objects.create(
        user=mgr, role=_role_with(['permissions.manage', 'users.view']))
    invalidate_capabilities(mgr.id)
    client.force_authenticate(mgr)

    boss = _user('boss@e.com')
    RoleAssignment.objects.create(
        user=boss, role=Role.objects.get(code=SUPERADMIN_ROLE_CODE))
    invalidate_capabilities(boss.id)
    # El delegado intenta dejar a boss sin superadmin (roles vacíos).
    resp = client.post(f'{USERS_URL}{boss.pk}/permissions/',
                       {'roles': []}, format='json')
    assert resp.status_code == 403
    assert resp.json()['codigo_error'] == 'CANNOT_GRANT_SUPERADMIN'
    assert is_superadmin(boss) is True


@pytest.mark.django_db
def test_superadmin_can_grant_superadmin(seeded, client):
    boss = _user('boss@e.com')
    RoleAssignment.objects.create(
        user=boss, role=Role.objects.get(code=SUPERADMIN_ROLE_CODE))
    invalidate_capabilities(boss.id)
    client.force_authenticate(boss)

    target = _user('promoted@e.com')
    superadmin_id = Role.objects.get(code=SUPERADMIN_ROLE_CODE).pk
    resp = client.post(f'{USERS_URL}{target.pk}/permissions/',
                       {'roles': [superadmin_id]}, format='json')
    assert resp.status_code == 200
    invalidate_capabilities(target.id)
    assert is_superadmin(target) is True
