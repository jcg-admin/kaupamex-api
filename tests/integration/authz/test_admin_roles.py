"""Integration — GET /api/v2/admin/roles (catálogo de roles, G-PERM-01).

El formulario admin ``/admin/permissions`` (UC-ADM-02) asigna roles a un
usuario vía ``POST /api/v2/admin/users/<pk>/permissions/`` (que espera ids de
Role). Hasta ahora no existía un endpoint para **listar el catálogo completo**
de roles disponibles: el selector solo podía leer los roles ya asignados a un
usuario (``AdminUserDetailSerializer.roles``). Este endpoint cierra ese gap.

Contrato: read-only, gateado por ``permissions.full`` (misma capacidad que
la asignación). Devuelve ``[{id, code, name, capabilities:[{code, level}]}]``
(DEC-11: sustantivo + nivel).
"""
from datetime import timedelta

from addons.authz.models import (
    AccessLevel, Capability, Module, Role, RoleAssignment,
    RoleCapability,
)
from addons.authz_reauth.models import ReauthSession
from addons.authz.services import (
    SUPERADMIN_ROLE_CODE, invalidate_capabilities, is_superadmin,
)

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

pytestmark = pytest.mark.integration

User = get_user_model()


@pytest.fixture
def seeded(db):
    call_command('seed_authz')


@pytest.fixture
def client():
    return APIClient()


def _auth(client, user):
    """Autentica y siembra una sesión reautenticada (DEC-12): editar permisos es
    una mutación **sensible** (``permissions.full``) que exige re-auth fresca.
    ``force_authenticate`` no crea sesión Django (``session_key=''``), así que la
    ventana se siembra para ese mismo key."""
    client.force_authenticate(user)
    ReauthSession.objects.update_or_create(
        user_id=user.pk, session_key='',
        defaults={'started_at': timezone.now(),
                  'expires_at': timezone.now() + timedelta(seconds=900)})


def _user(email):
    return User.objects.create_user(email=email, password='x')


def _grant(role, code, level=AccessLevel.FULL):
    module, _ = Module.objects.get_or_create(
        code=code.split('.', 1)[0], defaults={'name': code})
    cap, _ = Capability.objects.get_or_create(
        code=code, defaults={'module': module, 'name': code})
    RoleCapability.objects.update_or_create(
        role=role, capability=cap, defaults={'level': level})
    return cap


def _role_with_levels(pairs, code='r', name='Rol'):
    role = Role.objects.create(code=code, name=name)
    for c, lvl in pairs:
        _grant(role, c, lvl)
    return role


@pytest.mark.django_db
def test_requires_auth(seeded, client):
    assert client.get('/api/v2/admin/roles/').status_code == 401


@pytest.mark.django_db
def test_forbidden_without_permissions_full(seeded, client):
    # Un usuario con otra capacidad (no permissions@FULL) recibe 403.
    u = _user('sup@e.com')
    RoleAssignment.objects.create(
        user=u, role=_role_with_levels([('support', AccessLevel.FULL)]))
    invalidate_capabilities(u.id)
    _auth(client,u)
    assert client.get('/api/v2/admin/roles/').status_code == 403


@pytest.mark.django_db
def test_lists_catalog_for_permissions_manager(seeded, client):
    u = _user('mgr@e.com')
    RoleAssignment.objects.create(
        user=u, role=_role_with_levels([('permissions', AccessLevel.FULL)]))
    invalidate_capabilities(u.id)
    _auth(client,u)

    resp = client.get('/api/v2/admin/roles/')
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    codes = {r['code'] for r in body}
    # El rol 'r' (no privilegiado) aparece en el catálogo...
    assert 'r' in codes
    # ...pero el rol superadmin NO: un delegado con permissions@FULL que no
    # es superadmin no debe poder descubrir ni asignar superadmin (contención
    # de escalada de privilegios). Ver test_manager_cannot_grant_superadmin.
    assert SUPERADMIN_ROLE_CODE not in codes

    # Contrato por item: id (para el POST de asignación), code, name, y la
    # lista de capacidades como {code, level} (DEC-11) que agrupa el rol.
    r = next(item for item in body if item['code'] == 'r')
    assert set(r.keys()) == {'id', 'code', 'name', 'capabilities'}
    assert isinstance(r['id'], int)
    assert r['capabilities'] == [{'code': 'permissions', 'level': 'FULL'}]


@pytest.mark.django_db
def test_superadmin_sees_catalog(seeded, client):
    u = _user('boss@e.com')
    RoleAssignment.objects.create(
        user=u, role=Role.objects.get(code=SUPERADMIN_ROLE_CODE))
    invalidate_capabilities(u.id)
    _auth(client,u)
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
        user=mgr, role=_role_with_levels([('permissions', AccessLevel.FULL), ('users', AccessLevel.VIEW)]))
    invalidate_capabilities(mgr.id)
    _auth(client,mgr)

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
        user=mgr, role=_role_with_levels([('permissions', AccessLevel.FULL), ('users', AccessLevel.VIEW)]))
    invalidate_capabilities(mgr.id)
    _auth(client,mgr)

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
    _auth(client,boss)

    target = _user('promoted@e.com')
    superadmin_id = Role.objects.get(code=SUPERADMIN_ROLE_CODE).pk
    resp = client.post(f'{USERS_URL}{target.pk}/permissions/',
                       {'roles': [superadmin_id]}, format='json')
    assert resp.status_code == 200
    invalidate_capabilities(target.id)
    assert is_superadmin(target) is True
