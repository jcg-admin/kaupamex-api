"""Integration — /api/v2/authz/me/capabilities + me/menu (DEC-08/09).

El menú admin se persiste (``ir_ui_menu``) y el endpoint lo poda por las
capacidades del usuario. Verifica: superadmin ve todo; un usuario de solo
``support.view`` ve únicamente su sección; sin capacidades el menú es vacío;
las secciones sin hijos visibles se descartan; requiere autenticación.
"""
from addons.authz.models import (
    AccessLevel, Capability, Module, Role, RoleAssignment,
    RoleCapability,
)
from addons.base.models import IrUiMenu
from addons.authz.services import SUPERADMIN_ROLE_CODE, invalidate_capabilities

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

pytestmark = pytest.mark.integration

User = get_user_model()

# Verbo CRUD → nivel mínimo (DEC-11). ``manage`` es alias legado del tope.
_VERB_LEVEL = {
    'view': AccessLevel.VIEW, 'create': AccessLevel.CREATE,
    'edit': AccessLevel.EDIT, 'full': AccessLevel.FULL,
}


@pytest.fixture
def seeded(db):
    call_command('seed_authz')
    call_command('seed_menu')


@pytest.fixture
def client():
    return APIClient()


def _user(email):
    return User.objects.create_user(login=email, password='x')


def _grant(role, code, level):
    module, _ = Module.objects.get_or_create(
        code=code.split('.', 1)[0], defaults={'name': code})
    cap, _ = Capability.objects.get_or_create(
        code=code, defaults={'module': module, 'name': code})
    RoleCapability.objects.update_or_create(
        role=role, capability=cap, defaults={'level': level})


def _role_with(codes, code='r', name='Rol'):
    """DEC-11: traduce códigos legados ``X.verbo`` a sustantivo ``X`` al nivel
    del verbo; las acciones nombradas (verbo no-CRUD) quedan como membresía."""
    role = Role.objects.create(code=code, name=name)
    for c in codes:
        noun, _, verb = c.partition('.')
        if verb in _VERB_LEVEL:               # sustantivo graduado
            _grant(role, noun, _VERB_LEVEL[verb])
        else:                                  # acción nombrada / sustantivo puro
            _grant(role, c, AccessLevel.FULL)
    return role


@pytest.mark.django_db
def test_requires_auth(seeded, client):
    assert client.get('/api/v2/authz/me/menu/').status_code == 401
    assert client.get('/api/v2/authz/me/capabilities/').status_code == 401


@pytest.mark.django_db
def test_capabilities_endpoint_returns_resolved_set(seeded, client):
    u = _user('sup@e.com')
    RoleAssignment.objects.create(user=u, role=_role_with(['support.full']))
    invalidate_capabilities(u.id)
    client.force_authenticate(u)
    body = client.get('/api/v2/authz/me/capabilities/').json()
    assert body['is_superadmin'] is False
    # DEC-11: support@FULL se expande a la escala de verbos (view<create<edit<full).
    assert body['capabilities'] == [
        'support.create', 'support.edit', 'support.full',
        'support.view',
    ]


@pytest.mark.django_db
def test_support_user_sees_only_its_section(seeded, client):
    u = _user('sup@e.com')
    RoleAssignment.objects.create(user=u, role=_role_with(['support.full']))
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
    """El agrupador nivel-1 «Reportes» vive DENTRO de la sección de su dominio.

    Antes existía un único ``grp-reportes`` colgado de Operaciones y gateado
    por un ``reports`` transversal. La referencia no lo hace así: el submenú
    Reporting cuelga del root de **su propia app** y lo gatea el grupo de esa
    app (``odoo19c: addons/stock`` → ``menu_warehouse_report`` con
    ``parent="stock.menu_stock_root"`` y ``groups="group_stock_manager"``).

    Así que un usuario ``orders.view`` ve Ventas con su agrupador Reportes y
    sus dos hijos —el mismo ``sale.report`` agrupado distinto— y **no** ve el
    RFM, que es análisis de clientes y lo gatea ``users``.
    """
    u = _user('rep@e.com')
    RoleAssignment.objects.create(user=u, role=_role_with(['orders.view']))
    invalidate_capabilities(u.id)
    client.force_authenticate(u)
    tree = client.get('/api/v2/authz/me/menu/').json()
    ventas = next(s for s in tree if s['label'] == 'Ventas')
    assert [c['label'] for c in ventas['children']] == [
        'Pedidos', 'Panel de pedidos', 'Reportes']
    reportes = ventas['children'][-1]
    assert reportes['route'] == ''  # agrupador nivel 1 sin ruta
    assert [g['label'] for g in reportes['children']] == ['Ventas', 'Top sellers']
    # El RFM NO aparece: es de otro dominio.
    assert 'Clientes' not in [s['label'] for s in tree]


@pytest.mark.django_db
def test_customer_report_is_gated_by_its_own_domain(seeded, client):
    """El contraejemplo del anterior: ``users.view`` ve el RFM, no el de ventas."""
    u = _user('crm@e.com')
    RoleAssignment.objects.create(user=u, role=_role_with(['users.view']))
    invalidate_capabilities(u.id)
    client.force_authenticate(u)
    tree = client.get('/api/v2/authz/me/menu/').json()
    clientes = next(s for s in tree if s['label'] == 'Clientes')
    reportes = next(c for c in clientes['children'] if c['label'] == 'Reportes')
    assert [g['label'] for g in reportes['children']] == ['Clientes RFM']
    assert 'Ventas' not in [s['label'] for s in tree]


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
    # Reseñas (UGC/moderación para marketing + comportamiento) vive en
    # Marketing, no en una sección "Catálogo social" aparte. «Preguntas» ya no
    # está: su capacidad murió con el addon ``questions`` y vuelve con el
    # cluster ``website_sale`` que lo hospeda (H-QUESTIONS-01).
    marketing = next(s for s in tree if s['label'] == 'Marketing')
    assert [i['label'] for i in marketing['children']] == [
        'Reseñas', 'Newsletter', 'Notificaciones',
        'Listas de deseos', 'Banners de portada']
    # Ventas cierra con su propio agrupador Reportes (dominio dueño).
    ventas = next(s for s in tree if s['label'] == 'Ventas')
    assert [i['label'] for i in ventas['children']][-1] == 'Reportes'


@pytest.mark.django_db
def test_banners_leaf_gated_by_banners_manage(seeded, client):
    """Placement invariant: la hoja Banners lleva la misma capacidad que su
    endpoint enforce (banners.manage). Un usuario banners.manage la ve; el
    menú nunca muestra un destino que daría 403."""
    u = _user('mkt@e.com')
    RoleAssignment.objects.create(user=u, role=_role_with(['banners.full']))
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
    RoleAssignment.objects.create(user=u, role=_role_with(['settings.full']))
    invalidate_capabilities(u.id)
    client.force_authenticate(u)
    tree = client.get('/api/v2/authz/me/menu/').json()
    config = next(s for s in tree if s['label'] == 'Configuración')
    contenido = next(i for i in config['children']
                     if i['label'] == 'Contenido estático')
    assert contenido['route'] == '/admin/content'


@pytest.mark.django_db
def test_seed_menu_is_idempotent(seeded):
    before = IrUiMenu.objects.count()
    call_command('seed_menu')
    assert IrUiMenu.objects.count() == before


@pytest.mark.django_db
def test_arbitrary_depth_0_1_2_3(seeded, client):
    """El árbol es adjacency-list + build recursivo: la profundidad no tiene
    límite por diseño. Se arma una cadena nivel 0→1→2→3 y el endpoint la
    devuelve anidada intacta (prueba de que 0/1/2/3/N funciona sin cambios)."""
    cap = Capability.objects.get(code='settings')
    n0 = IrUiMenu.objects.create(key='d0', name='N0', route='', sequence=90)
    n1 = IrUiMenu.objects.create(key='d1', name='N1', route='', sequence=0, parent=n0)
    n2 = IrUiMenu.objects.create(key='d2', name='N2', route='', sequence=0, parent=n1)
    IrUiMenu.objects.create(key='d3', name='N3', route='/admin/system-settings',
                            sequence=0, parent=n2, group=cap)

    u = _user('deep@e.com')
    RoleAssignment.objects.create(user=u, role=_role_with(['settings.full']))
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
