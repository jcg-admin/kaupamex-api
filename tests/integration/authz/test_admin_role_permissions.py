"""Integration — editor de permisos por rol (UC-ADM-02, H-UI-PERM-01, DEC-11).

La UI ``/admin/permissions`` (``AdminPermissionsPage``) es una matriz
roles×sustantivo×nivel: consume ``GET /api/v2/admin/permissions/`` para pintarla
y ``PUT /api/v2/admin/roles/<code>/permissions/`` para guardar el set graduado
de cada rol. Contención de escalada **por nivel**: un delegado con
``permissions.full`` solo puede conceder un sustantivo hasta SU propio nivel en
ese sustantivo (y solo las acciones nombradas que posee); el superadmin no tiene
ese límite y su rol solo lo edita otro superadmin.
"""
from datetime import timedelta

from addons.authz.models import (
    AccessLevel, Capability, Module, Role, RoleAssignment,
    RoleCapability,
)
from addons.authz_reauth.models import ReauthSession
from addons.authz.services import (
    SUPERADMIN_ROLE_CODE, invalidate_capabilities, resolve_capabilities,
)

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

pytestmark = pytest.mark.integration

User = get_user_model()

CATALOG_URL = '/api/v2/admin/permissions/'


def _auth(client, user):
    """Autentica y siembra una sesión reautenticada (DEC-12): guardar el set de
    permisos de un rol es una mutación **sensible** (``permissions.full``) que
    exige re-auth fresca. ``force_authenticate`` no crea sesión Django
    (``session_key=''``), así que la ventana se siembra para ese key."""
    client.force_authenticate(user)
    ReauthSession.objects.update_or_create(
        user_id=user.pk, session_key='',
        defaults={'started_at': timezone.now(),
                  'expires_at': timezone.now() + timedelta(seconds=900)})


def _role_url(code):
    return f'/api/v2/admin/roles/{code}/permissions/'


@pytest.fixture
def seeded(db):
    call_command('seed_authz')


@pytest.fixture
def client():
    return APIClient()


def _user(email):
    return User.objects.create_user(login=email, password='x')


def _grant(role, code, level=AccessLevel.FULL):
    """Concede ``code`` al rol al nivel dado. Sustantivo (sin punto) usa el
    nivel; acción nombrada (con punto) es membresía (FULL). Idempotente."""
    module, _ = Module.objects.get_or_create(
        code=code.split('.', 1)[0], defaults={'name': code},
    )
    cap, _ = Capability.objects.get_or_create(
        code=code, defaults={'module': module, 'name': code},
    )
    RoleCapability.objects.update_or_create(
        role=role, capability=cap, defaults={'level': level},
    )
    return cap


def _role_with_levels(pairs, code='r', name='Rol'):
    """``pairs``: lista de ``(code, AccessLevel)``."""
    role = Role.objects.create(code=code, name=name)
    for c, lvl in pairs:
        _grant(role, c, lvl)
    return role


def _manager(client):
    # Delegado: permissions@FULL (pasa el gate) + users@VIEW (techo de escalada).
    u = _user('mgr@e.com')
    RoleAssignment.objects.create(user=u, role=_role_with_levels(
        [('permissions', AccessLevel.FULL), ('users', AccessLevel.VIEW)],
        code='mgr-role'))
    invalidate_capabilities(u.id)
    _auth(client,u)
    return u


def _superadmin(client):
    u = _user('boss@e.com')
    RoleAssignment.objects.create(
        user=u, role=Role.objects.get(code=SUPERADMIN_ROLE_CODE))
    invalidate_capabilities(u.id)
    _auth(client,u)
    return u


# ─────────────────────────── GET /admin/permissions/ ───────────────────────

@pytest.mark.django_db
def test_catalog_requires_auth(seeded, client):
    assert client.get(CATALOG_URL).status_code == 401


@pytest.mark.django_db
def test_catalog_forbidden_without_permissions_full(seeded, client):
    u = _user('sup@e.com')
    RoleAssignment.objects.create(
        user=u, role=_role_with_levels([('support', AccessLevel.FULL)]))
    invalidate_capabilities(u.id)
    _auth(client,u)
    assert client.get(CATALOG_URL).status_code == 403


@pytest.mark.django_db
def test_catalog_shape_for_manager(seeded, client):
    _manager(client)
    _role_with_levels([('users', AccessLevel.VIEW)], code='viewer', name='Visor')

    resp = client.get(CATALOG_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {'roles', 'permissions'}

    # roles: lista de {role, permissions:[{code, level}]}; superadmin oculto.
    role_codes = {r['role'] for r in body['roles']}
    assert 'viewer' in role_codes
    assert SUPERADMIN_ROLE_CODE not in role_codes
    viewer = next(r for r in body['roles'] if r['role'] == 'viewer')
    assert viewer['permissions'] == [{'code': 'users', 'level': 'VIEW'}]

    # grantables: los nouns propios con su nivel como techo.
    assert body['permissions'] == [
        {'code': 'permissions', 'level': 'FULL'},
        {'code': 'users', 'level': 'VIEW'},
    ]


@pytest.mark.django_db
def test_catalog_superadmin_sees_all(seeded, client):
    _superadmin(client)
    resp = client.get(CATALOG_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert SUPERADMIN_ROLE_CODE in {r['role'] for r in body['roles']}
    # El catálogo de grantables cubre todas las capacidades activas.
    all_active = set(
        Capability.objects.filter(is_active=True).values_list('code', flat=True))
    assert {p['code'] for p in body['permissions']} == all_active
    # Sustantivos a FULL; acciones nombradas con level null.
    by_code = {p['code']: p['level'] for p in body['permissions']}
    assert by_code['users'] == 'FULL'
    assert by_code['account.profile'] is None
    # Ordenado por code (contrato estable).
    codes = [p['code'] for p in body['permissions']]
    assert codes == sorted(codes)


# ──────────────────── PUT /admin/roles/<code>/permissions/ ──────────────────

@pytest.mark.django_db
def test_put_requires_auth(seeded, client):
    _role_with_levels([], code='r')
    assert client.put(_role_url('r'), {'permissions': []},
                      format='json').status_code == 401


@pytest.mark.django_db
def test_put_forbidden_without_permissions_full(seeded, client):
    u = _user('sup@e.com')
    RoleAssignment.objects.create(
        user=u, role=_role_with_levels([('support', AccessLevel.FULL)]))
    invalidate_capabilities(u.id)
    _auth(client,u)
    _role_with_levels([], code='target')
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
                      {'permissions': [{'code': 'users', 'level': 'VIEW'}]},
                      format='json')
    assert resp.status_code == 403
    assert resp.json()['codigo_error'] == 'CANNOT_EDIT_SUPERADMIN'


@pytest.mark.django_db
def test_put_unknown_capability_400(seeded, client):
    _manager(client)
    _role_with_levels([], code='target')
    resp = client.put(_role_url('target'),
                      {'permissions': [{'code': 'nonexistent', 'level': 'VIEW'}]},
                      format='json')
    assert resp.status_code == 400
    assert resp.json()['codigo_error'] == 'UNKNOWN_CAPABILITY'


@pytest.mark.django_db
def test_put_noun_without_level_400(seeded, client):
    # DEC-11: un sustantivo exige 'level'. Payload inválido → 400.
    _manager(client)
    _role_with_levels([], code='target')
    resp = client.put(_role_url('target'),
                      {'permissions': [{'code': 'users'}]}, format='json')
    assert resp.status_code == 400
    assert resp.json()['codigo_error'] == 'INVALID_PAYLOAD'


@pytest.mark.django_db
def test_put_manager_cannot_grant_unheld_noun(seeded, client):
    # El delegado tiene {permissions@FULL, users@VIEW}; intenta conceder el
    # sustantivo 'support' que NO posee → escalada.
    _manager(client)
    _role_with_levels([], code='target')
    resp = client.put(_role_url('target'),
                      {'permissions': [{'code': 'support', 'level': 'VIEW'}]},
                      format='json')
    assert resp.status_code == 403
    assert resp.json()['codigo_error'] == 'CANNOT_GRANT_UNHELD_CAPABILITY'
    assert Role.objects.get(code='target').capabilities.count() == 0


@pytest.mark.django_db
def test_put_manager_cannot_grant_above_own_level(seeded, client):
    # El delegado tiene users@VIEW; conceder users@FULL excede su techo → 403.
    _manager(client)
    _role_with_levels([], code='target')
    resp = client.put(_role_url('target'),
                      {'permissions': [{'code': 'users', 'level': 'FULL'}]},
                      format='json')
    assert resp.status_code == 403
    assert resp.json()['codigo_error'] == 'CANNOT_GRANT_UNHELD_CAPABILITY'
    assert Role.objects.get(code='target').capabilities.count() == 0


@pytest.mark.django_db
def test_put_manager_grants_at_or_below_own_level(seeded, client):
    # users@VIEW está dentro del techo del delegado (users@VIEW) → 200.
    _manager(client)
    _role_with_levels([], code='target')
    resp = client.put(_role_url('target'),
                      {'permissions': [{'code': 'users', 'level': 'VIEW'}]},
                      format='json')
    assert resp.status_code == 200
    assert resp.json() == {
        'role': 'target',
        'permissions': [{'code': 'users', 'level': 'VIEW'}],
    }
    rc = RoleCapability.objects.get(
        role__code='target', capability__code='users')
    assert rc.level == AccessLevel.VIEW


@pytest.mark.django_db
def test_put_preserves_frozen_capabilities(seeded, client):
    # 'target' ya tiene support@FULL (que el delegado NO controla). El delegado
    # agrega users@VIEW (que sí controla) SIN tocar la congelada → OK, y la
    # congelada se preserva (support en current == support en desired).
    _manager(client)
    _role_with_levels([('support', AccessLevel.FULL)], code='target')
    resp = client.put(
        _role_url('target'),
        {'permissions': [{'code': 'support', 'level': 'FULL'},
                         {'code': 'users', 'level': 'VIEW'}]}, format='json')
    assert resp.status_code == 200
    have = {rc.capability.code: rc.level for rc in
            RoleCapability.objects.filter(role__code='target')
            .select_related('capability')}
    assert have == {'support': AccessLevel.FULL, 'users': AccessLevel.VIEW}


@pytest.mark.django_db
def test_put_manager_cannot_revoke_frozen_capability(seeded, client):
    # Quitar support@FULL (que el delegado no controla) es también escalada.
    _manager(client)
    _role_with_levels([('support', AccessLevel.FULL)], code='target')
    resp = client.put(_role_url('target'), {'permissions': []}, format='json')
    assert resp.status_code == 403
    assert resp.json()['codigo_error'] == 'CANNOT_GRANT_UNHELD_CAPABILITY'
    rc = RoleCapability.objects.get(
        role__code='target', capability__code='support')
    assert rc.level == AccessLevel.FULL


@pytest.mark.django_db
def test_put_manager_cannot_lower_frozen_capability(seeded, client):
    # Bajar support@FULL a support@VIEW (fuera del control del delegado) → 403.
    _manager(client)
    _role_with_levels([('support', AccessLevel.FULL)], code='target')
    resp = client.put(
        _role_url('target'),
        {'permissions': [{'code': 'support', 'level': 'VIEW'}]}, format='json')
    assert resp.status_code == 403
    assert resp.json()['codigo_error'] == 'CANNOT_GRANT_UNHELD_CAPABILITY'


@pytest.mark.django_db
def test_put_superadmin_sets_any_capabilities(seeded, client):
    _superadmin(client)
    _role_with_levels([], code='target')
    resp = client.put(
        _role_url('target'),
        {'permissions': [{'code': 'support', 'level': 'FULL'},
                         {'code': 'users', 'level': 'CREATE'}]}, format='json')
    assert resp.status_code == 200
    have = {rc.capability.code: rc.level for rc in
            RoleCapability.objects.filter(role__code='target')
            .select_related('capability')}
    assert have == {'support': AccessLevel.FULL, 'users': AccessLevel.CREATE}


@pytest.mark.django_db
def test_put_named_action_is_membership(seeded, client):
    # Una acción nombrada se concede por membresía; su level se ignora.
    _superadmin(client)
    _role_with_levels([], code='target')
    resp = client.put(
        _role_url('target'),
        {'permissions': [{'code': 'account.profile'}]}, format='json')
    assert resp.status_code == 200
    assert resp.json()['permissions'] == [
        {'code': 'account.profile', 'level': None}]
    rc = RoleCapability.objects.get(
        role__code='target', capability__code='account.profile')
    assert rc.level == AccessLevel.FULL


@pytest.mark.django_db
def test_put_invalidates_assignee_capability_cache(seeded, client):
    # Un usuario tiene el rol 'target'; al mutar el rol, su set efectivo cambia.
    _superadmin(client)
    role = _role_with_levels([('users', AccessLevel.VIEW)], code='target')
    assignee = _user('assignee@e.com')
    RoleAssignment.objects.create(user=assignee, role=role)
    # Poblar la cache del assignee con el estado viejo.
    assert 'users.view' in resolve_capabilities(assignee)

    resp = client.put(
        _role_url('target'),
        {'permissions': [{'code': 'users', 'level': 'VIEW'},
                         {'code': 'support', 'level': 'FULL'}]}, format='json')
    assert resp.status_code == 200
    # Sin invalidación, resolve_capabilities devolvería el set cacheado viejo.
    assert 'support.full' in resolve_capabilities(assignee)
