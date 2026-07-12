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
from apps.authz.services import SUPERADMIN_ROLE_CODE, invalidate_capabilities

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
    # seed_authz siembra al menos el rol superadmin; el rol 'r' recién creado
    # también aparece en el catálogo completo.
    codes = {r['code'] for r in body}
    assert SUPERADMIN_ROLE_CODE in codes
    assert 'r' in codes

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
    # El superadmin (que posee permissions.manage vía todas las capacidades)
    # ve el catálogo. Los items están ordenados por code (contrato estable).
    codes = [r['code'] for r in resp.json()]
    assert codes == sorted(codes)
