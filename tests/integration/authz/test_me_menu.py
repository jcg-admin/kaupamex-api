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
    # Solo la sección Clientes sobrevive; support.manage gatea Soporte y
    # Mensajes de contacto (ambos support.manage).
    assert [s['label'] for s in tree] == ['Clientes']
    leaves = [i['label'] for i in tree[0]['children']]
    assert leaves == ['Soporte (Tickets)', 'Mensajes de contacto']


@pytest.mark.django_db
def test_level_two_group_is_nested(seeded, client):
    """Un usuario reports.view ve la sección Operaciones con el agrupador
    nivel-1 Reportes y sus 4 hijos nivel-2 (los demás items de Operaciones,
    que requieren otras capacidades, se podan)."""
    u = _user('rep@e.com')
    RoleAssignment.objects.create(user=u, role=_role_with(['reports.view']))
    invalidate_capabilities(u.id)
    client.force_authenticate(u)
    tree = client.get('/api/v2/authz/me/menu/').json()
    labels = [s['label'] for s in tree]
    # Dashboard (Principal) y Reportes (Operaciones) usan reports.view.
    assert 'Operaciones' in labels
    ops = next(s for s in tree if s['label'] == 'Operaciones')
    # Solo sobrevive el agrupador Reportes (los otros items son de otro dominio).
    assert [c['label'] for c in ops['children']] == ['Reportes']
    reportes = ops['children'][0]
    assert reportes['route'] == ''  # agrupador nivel 1 sin ruta
    assert [g['label'] for g in reportes['children']] == [
        'Dashboard', 'Ventas', 'Top sellers', 'Clientes RFM']


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
    assert labels == ['Principal', 'Catálogo', 'Ventas', 'Marketing',
                      'Clientes', 'Operaciones', 'Sistema', 'Configuración']
    # Catálogo tiene sus 5 items visibles para el superadmin.
    catalogo = next(s for s in tree if s['label'] == 'Catálogo')
    assert [i['label'] for i in catalogo['children']] == [
        'Productos', 'Crear Producto', 'Categorías', 'Descuentos',
        'Sincronización de precios']
    # Reseñas y Preguntas (UGC/moderación para marketing + comportamiento)
    # viven en Marketing, no en una sección "Catálogo social" aparte.
    marketing = next(s for s in tree if s['label'] == 'Marketing')
    assert [i['label'] for i in marketing['children']] == [
        'Reseñas', 'Preguntas', 'Newsletter', 'Notificaciones',
        'Listas de deseos', 'Banners de portada']


@pytest.mark.django_db
def test_banners_leaf_gated_by_banners_manage(seeded, client):
    """Placement invariant: la hoja Banners lleva la misma capacidad que su
    endpoint enforce (banners.manage). Un usuario banners.manage la ve; el
    menú nunca muestra un destino que daría 403."""
    u = _user('mkt@e.com')
    RoleAssignment.objects.create(user=u, role=_role_with(['banners.manage']))
    invalidate_capabilities(u.id)
    client.force_authenticate(u)
    tree = client.get('/api/v2/authz/me/menu/').json()
    marketing = next(s for s in tree if s['label'] == 'Marketing')
    banners = next(i for i in marketing['children']
                   if i['label'] == 'Banners de portada')
    assert banners['route'] == '/admin/banners'


@pytest.mark.django_db
def test_static_content_leaf_gated_by_settings_manage(seeded, client):
    """UC-CFG-04: la hoja «Contenido estático» lleva settings.manage — la misma
    capacidad que /api/v2/admin/pages/ enforce. Cierra el gap endpoint↔menu↔UI:
    el CRUD de páginas existía pero no tenía destino en el menú."""
    u = _user('cfg@e.com')
    RoleAssignment.objects.create(user=u, role=_role_with(['settings.manage']))
    invalidate_capabilities(u.id)
    client.force_authenticate(u)
    tree = client.get('/api/v2/authz/me/menu/').json()
    config = next(s for s in tree if s['label'] == 'Configuración')
    contenido = next(i for i in config['children']
                     if i['label'] == 'Contenido estático')
    assert contenido['route'] == '/admin/content'


@pytest.mark.django_db
def test_seed_menu_is_idempotent(seeded):
    before = MenuItem.objects.count()
    call_command('seed_menu')
    assert MenuItem.objects.count() == before


@pytest.mark.django_db
def test_arbitrary_depth_0_1_2_3(seeded, client):
    """El árbol es adjacency-list + build recursivo: la profundidad no tiene
    límite por diseño. Se arma una cadena nivel 0→1→2→3 y el endpoint la
    devuelve anidada intacta (prueba de que 0/1/2/3/N funciona sin cambios)."""
    cap = Capability.objects.get(code='settings.manage')
    n0 = MenuItem.objects.create(key='d0', label='N0', route='', order=90)
    n1 = MenuItem.objects.create(key='d1', label='N1', route='', order=0, parent=n0)
    n2 = MenuItem.objects.create(key='d2', label='N2', route='', order=0, parent=n1)
    MenuItem.objects.create(key='d3', label='N3', route='/admin/system-settings',
                            order=0, parent=n2, required_capability=cap)

    u = _user('deep@e.com')
    RoleAssignment.objects.create(user=u, role=_role_with(['settings.manage']))
    invalidate_capabilities(u.id)
    client.force_authenticate(u)
    tree = client.get('/api/v2/authz/me/menu/').json()

    n0node = next(s for s in tree if s['label'] == 'N0')          # nivel 0
    n1node = n0node['children'][0]                                 # nivel 1
    n2node = n1node['children'][0]                                 # nivel 2
    n3node = n2node['children'][0]                                 # nivel 3
    assert [n1node['label'], n2node['label'], n3node['label']] == ['N1', 'N2', 'N3']
    assert n3node['route'] == '/admin/system-settings'
    assert n3node['children'] == []
