"""Integration — /api/v2/authz/me/capabilities + me/menu (DEC-08/09).

El menú admin se persiste (``authz_menu_item``) y el endpoint lo poda por las
capacidades del usuario. Verifica: superadmin ve todo; un usuario de solo
``support.view`` ve únicamente su sección; sin capacidades el menú es vacío;
las secciones sin hijos visibles se descartan; requiere autenticación.
"""
from apps.authz.models import Capability, MenuItem, Role, RoleAssignment
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
    call_command('seed_menu')


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
    assert client.get('/api/v2/authz/me/menu/').status_code == 401
    assert client.get('/api/v2/authz/me/capabilities/').status_code == 401


@pytest.mark.django_db
def test_capabilities_endpoint_returns_resolved_set(seeded, client):
    u = _user('sup@e.com')
    RoleAssignment.objects.create(user=u, role=_role_with(['support.manage']))
    invalidate_capabilities(u.id)
    client.force_authenticate(u)
    body = client.get('/api/v2/authz/me/capabilities/').json()
    assert body['is_superadmin'] is False
    assert body['capabilities'] == ['support.manage']


@pytest.mark.django_db
def test_support_user_sees_only_its_section(seeded, client):
    u = _user('sup@e.com')
    RoleAssignment.objects.create(user=u, role=_role_with(['support.manage']))
    invalidate_capabilities(u.id)
    client.force_authenticate(u)
    tree = client.get('/api/v2/authz/me/menu/').json()
    # Solo la sección Clientes sobrevive, con un único hijo visible (Soporte).
    assert [s['label'] for s in tree] == ['Clientes']
    leaves = [i['label'] for i in tree[0]['children']]
    assert leaves == ['Soporte (Tickets)']
    assert tree[0]['children'][0]['route'] == '/admin/support'


@pytest.mark.django_db
def test_no_capabilities_yields_empty_menu(seeded, client):
    u = _user('nobody@e.com')
    client.force_authenticate(u)
    assert client.get('/api/v2/authz/me/menu/').json() == []


@pytest.mark.django_db
def test_superadmin_sees_all_sections(seeded, client):
    u = _user('boss@e.com')
    RoleAssignment.objects.create(
        user=u, role=Role.objects.get(code=SUPERADMIN_ROLE_CODE))
    invalidate_capabilities(u.id)
    client.force_authenticate(u)
    tree = client.get('/api/v2/authz/me/menu/').json()
    labels = [s['label'] for s in tree]
    assert labels == ['Principal', 'Catálogo', 'Ventas', 'Clientes',
                      'Operaciones', 'Sistema', 'Configuración']
    # Catálogo tiene sus 3 items visibles para el superadmin.
    catalogo = next(s for s in tree if s['label'] == 'Catálogo')
    assert [i['label'] for i in catalogo['children']] == [
        'Productos', 'Crear Producto', 'Categorías']


@pytest.mark.django_db
def test_seed_menu_is_idempotent(seeded):
    before = MenuItem.objects.count()
    call_command('seed_menu')
    assert MenuItem.objects.count() == before
