"""
Tests — Admin product listing filters, search, and restore

Cubre dos defectos reportados en QA del panel admin:

- H-ADMIN-FILTER: ``ProductAdminViewSet`` ignoraba ``?filter=`` y ``?search=``
  (no tenía ``get_queryset`` ni filter backends), así que "Sin stock",
  "Borradores" y "Publicados" devolvían el catálogo completo.
- H-ADMIN-RESTORE: no existía endpoint para reactivar un producto tras el
  soft-delete. El botón "Reactivar producto" del UI pegaba a una ruta
  inexistente → 404 ("Request failed not found"). Además el manager por
  defecto (``objects``) excluye ``is_deleted=True``, así que ni el detalle del
  producto borrado era alcanzable.
"""
import pytest
from decimal import Decimal
from apps.modules.catalogue.models import Category, Product

pytestmark = pytest.mark.integration

ADMIN_PROD_URL = '/api/v2/admin/products/'


@pytest.fixture
def cat_admin(db):
    return Category.objects.create(name='Admin Cat', slug='admin-cat', is_active=True)


@pytest.fixture
def mix_productos(db, cat_admin):
    """3 estados distintos para ejercitar los filtros del listado admin."""
    publicado = Product.objects.create(
        name='Collar Publicado', slug='collar-publicado', sku='PUB-001',
        description='visible', price=Decimal('900.00'), stock=5,
        is_active=True, is_published=True,
    )
    borrador = Product.objects.create(
        name='Collar Borrador', slug='collar-borrador', sku='DRAFT-001',
        description='oculto', price=Decimal('900.00'), stock=5,
        is_active=True, is_published=False,
    )
    sin_stock = Product.objects.create(
        name='Collar Agotado', slug='collar-agotado', sku='OOS-001',
        description='agotado', price=Decimal('900.00'), stock=0,
        is_active=True, is_published=True,
    )
    for p in (publicado, borrador, sin_stock):
        p.categories.add(cat_admin)
    return {'publicado': publicado, 'borrador': borrador, 'sin_stock': sin_stock}


def _names(res):
    """Extrae los nombres de la respuesta (paginada o lista plana)."""
    data = res.data
    rows = data['results'] if isinstance(data, dict) and 'results' in data else data
    return {row['name'] for row in rows}


# =============================================================================
# H-ADMIN-FILTER — filtros de listado (?filter=)
# =============================================================================

class TestAdminProductFilters:

    def test_sin_filtro_devuelve_todos(self, admin_client, mix_productos):
        res = admin_client.get(ADMIN_PROD_URL)
        assert res.status_code == 200
        names = _names(res)
        assert {'Collar Publicado', 'Collar Borrador', 'Collar Agotado'} <= names

    def test_filter_published_solo_publicados(self, admin_client, mix_productos):
        res = admin_client.get(ADMIN_PROD_URL, {'filter': 'published'})
        assert res.status_code == 200
        names = _names(res)
        assert 'Collar Publicado' in names
        assert 'Collar Borrador' not in names

    def test_filter_draft_solo_borradores(self, admin_client, mix_productos):
        res = admin_client.get(ADMIN_PROD_URL, {'filter': 'draft'})
        assert res.status_code == 200
        names = _names(res)
        assert 'Collar Borrador' in names
        assert 'Collar Publicado' not in names

    def test_filter_out_of_stock_solo_agotados(self, admin_client, mix_productos):
        res = admin_client.get(ADMIN_PROD_URL, {'filter': 'out_of_stock'})
        assert res.status_code == 200
        names = _names(res)
        assert names == {'Collar Agotado'}

    def test_filter_desconocido_no_rompe(self, admin_client, mix_productos):
        """Un filtro no reconocido cae a 'all' (no error)."""
        res = admin_client.get(ADMIN_PROD_URL, {'filter': 'zzz'})
        assert res.status_code == 200
        assert len(_names(res)) >= 3


# =============================================================================
# H-ADMIN-FILTER — búsqueda (?search=)
# =============================================================================

class TestAdminProductSearch:

    def test_search_por_nombre(self, admin_client, mix_productos):
        res = admin_client.get(ADMIN_PROD_URL, {'search': 'Agotado'})
        assert res.status_code == 200
        assert _names(res) == {'Collar Agotado'}

    def test_search_por_sku(self, admin_client, mix_productos):
        res = admin_client.get(ADMIN_PROD_URL, {'search': 'DRAFT-001'})
        assert res.status_code == 200
        assert _names(res) == {'Collar Borrador'}

    def test_search_sin_coincidencias(self, admin_client, mix_productos):
        res = admin_client.get(ADMIN_PROD_URL, {'search': 'noexiste-xyz'})
        assert res.status_code == 200
        assert _names(res) == set()


# =============================================================================
# H-ADMIN-RESTORE — reactivar producto (contraparte de deactivate)
# =============================================================================

class TestAdminProductActivate:

    def _deactivate(self, admin_client, prod):
        """Desactiva vía el endpoint real (requiere confirm:true)."""
        admin_client.post(f'{ADMIN_PROD_URL}{prod.pk}/deactivate/', {'confirm': True}, format='json')
        prod.refresh_from_db()
        assert prod.is_active is False

    def test_producto_borrado_no_aparece_en_listado(self, admin_client, mix_productos):
        prod = mix_productos['publicado']
        admin_client.delete(f'{ADMIN_PROD_URL}{prod.pk}/')
        res = admin_client.get(ADMIN_PROD_URL)
        assert 'Collar Publicado' not in _names(res)

    def test_activate_reactiva_producto_desactivado(self, admin_client, mix_productos):
        prod = mix_productos['publicado']
        self._deactivate(admin_client, prod)

        res = admin_client.post(f'{ADMIN_PROD_URL}{prod.pk}/activate/')
        assert res.status_code == 200

        prod.refresh_from_db()
        assert prod.is_active is True

    def test_activate_producto_ya_activo_devuelve_400(self, admin_client, mix_productos):
        prod = mix_productos['publicado']  # nace is_active=True
        res = admin_client.post(f'{ADMIN_PROD_URL}{prod.pk}/activate/')
        assert res.status_code == 400
        assert res.data['codigo_error'] == 'PRODUCTO_YA_ACTIVO'

    def test_activate_producto_inexistente_devuelve_404(self, admin_client, db):
        res = admin_client.post(f'{ADMIN_PROD_URL}999999/activate/')
        assert res.status_code == 404

    def test_activate_requiere_admin(self, api_client, mix_productos):
        prod = mix_productos['publicado']
        res = api_client.post(f'{ADMIN_PROD_URL}{prod.pk}/activate/')
        assert res.status_code in (401, 403)
