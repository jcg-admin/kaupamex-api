"""
Tests — Admin product deactivation and bulk price sync

UC-CAT-11: Deactivate product with impact preview
UC-CAT-12: Bulk price sync (CSV upload and percentage adjustment)
"""
import csv, io, pytest
from decimal import Decimal
from apps.catalogue.models import Category, Product
from django.core.cache import cache

pytestmark = pytest.mark.integration

ADMIN_PROD_URL    = '/api/v1/admin/products/'
PRICE_SYNC_URL    = '/api/v1/admin/products/price-sync/'
PRICE_CONFIRM_URL = '/api/v1/admin/products/price-sync/confirm/'
PRICE_TMPL_URL    = '/api/v1/admin/products/price-sync/template/'


@pytest.fixture
def cat_soperas(db):
    return Category.objects.create(name='Soperas S8', slug='soperas-s8', is_active=True)


@pytest.fixture
def product_activo(db, cat_soperas):
    _p = Product.objects.create(
        name='Sopera Yemaya S8', slug='sopera-yemaya-s8', sku='S8-YEM-001',
        description='',
        price=Decimal('3200.00'), stock=7,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_soperas)
    return _p


@pytest.fixture
def product_sin_stock(db, cat_soperas):
    _p = Product.objects.create(
        name='Producto Sin Stock', slug='sin-stock-s8', sku='S8-NST-001',
        description='',
        price=Decimal('1000.00'), stock=0,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_soperas)
    return _p


def _make_csv(rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['sku', 'price'])
    for sku, price in rows:
        w.writerow([sku, price])
    buf.seek(0)
    return io.BytesIO(buf.read().encode())


# =============================================================================
# UC-CAT-11 — Desactivar producto con preview de impacto
# =============================================================================

class TestDesactivarProducto:

    def test_preview_sin_confirm_retorna_200_con_impacto(
        self, admin_client, product_activo, db
    ):
        """Sin confirm=True → solo preview, sin modificar el producto."""
        res = admin_client.post(
            f'{ADMIN_PROD_URL}{product_activo.pk}/deactivate/', {}, format='json'
        )
        assert res.status_code == 200
        data = res.json()
        assert data['stock'] == 7
        assert 'confirm' in data['message'].lower()
        product_activo.refresh_from_db()
        assert product_activo.is_active is True  # sin cambios

    def test_preview_con_confirm_desactiva(self, admin_client, product_activo, db):
        """Con confirm=True → desactiva el producto."""
        res = admin_client.post(
            f'{ADMIN_PROD_URL}{product_activo.pk}/deactivate/',
            {'confirm': True}, format='json'
        )
        assert res.status_code == 200
        assert res.json()['is_active'] is False
        product_activo.refresh_from_db()
        assert product_activo.is_active is False
        assert product_activo.is_published is False

    def test_desactivar_purga_cache_ficha(self, admin_client, product_activo, db):
        cache.set(f'product:{product_activo.pk}:detail', {'dummy': 1}, 300)
        admin_client.post(
            f'{ADMIN_PROD_URL}{product_activo.pk}/deactivate/',
            {'confirm': True}, format='json'
        )
        assert cache.get(f'product:{product_activo.pk}:detail') is None

    def test_desactivar_purga_cache_arbol(self, admin_client, product_activo, db):
        cache.set('categories:tree', [{'stale': True}], 300)
        admin_client.post(
            f'{ADMIN_PROD_URL}{product_activo.pk}/deactivate/',
            {'confirm': True}, format='json'
        )
        assert cache.get('categories:tree') is None

    def test_desactivar_producto_ya_inactivo_retorna_400(
        self, admin_client, product_activo, db
    ):
        product_activo.is_active = False
        product_activo.save()
        res = admin_client.post(
            f'{ADMIN_PROD_URL}{product_activo.pk}/deactivate/',
            {'confirm': True}, format='json'
        )
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'PRODUCTO_YA_INACTIVO'

    def test_desactivar_sin_auth_retorna_401(self, api_client, product_activo, db):
        res = api_client.post(
            f'{ADMIN_PROD_URL}{product_activo.pk}/deactivate/',
            {'confirm': True}, format='json'
        )
        assert res.status_code == 401

    def test_impacto_muestra_stock_correcto(self, admin_client, product_activo, db):
        res = admin_client.post(
            f'{ADMIN_PROD_URL}{product_activo.pk}/deactivate/', {}, format='json'
        )
        assert res.json()['stock'] == product_activo.stock

    def test_delete_endpoint_tambien_purga_cache_ficha(
        self, admin_client, product_activo, db
    ):
        """perform_destroy mejorado en Sprint 8 también purga product:{pk}:detail."""
        cache.set(f'product:{product_activo.pk}:detail', {'dummy': 1}, 300)
        admin_client.delete(f'{ADMIN_PROD_URL}{product_activo.pk}/')
        assert cache.get(f'product:{product_activo.pk}:detail') is None


# =============================================================================
# UC-CAT-12 — Sincronizar precios CSV
# =============================================================================

class TestSincronizarPreciosCSV:

    def test_upload_csv_valido_retorna_preview(
        self, admin_client, product_activo, db
    ):
        csv_file = _make_csv([(product_activo.sku, '3500.00')])
        res = admin_client.post(
            PRICE_SYNC_URL,
            {'file': csv_file},
            format='multipart',
        )
        assert res.status_code == 200
        data = res.json()
        assert data['valid_count'] == 1
        assert data['invalid_count'] == 0
        assert 'session_id' in data

    def test_csv_sku_no_encontrado_va_a_errores(self, admin_client, db):
        csv_file = _make_csv([('NO-EXISTE-SKU', '100.00')])
        res = admin_client.post(PRICE_SYNC_URL, {'file': csv_file}, format='multipart')
        assert res.status_code == 200
        assert res.json()['valid_count'] == 0
        assert res.json()['invalid_count'] == 1

    def test_csv_precio_invalido_va_a_errores(self, admin_client, product_activo, db):
        csv_file = _make_csv([(product_activo.sku, 'no-es-numero')])
        res = admin_client.post(PRICE_SYNC_URL, {'file': csv_file}, format='multipart')
        assert res.status_code == 200
        assert res.json()['invalid_count'] == 1

    def test_confirm_aplica_los_cambios(self, admin_client, product_activo, db):
        csv_file = _make_csv([(product_activo.sku, '4000.00')])
        preview = admin_client.post(
            PRICE_SYNC_URL, {'file': csv_file}, format='multipart'
        )
        session_id = preview.json()['session_id']
        confirm = admin_client.post(
            PRICE_CONFIRM_URL, {'session_id': session_id}, format='json'
        )
        assert confirm.status_code == 200
        assert confirm.json()['updated_count'] == 1
        product_activo.refresh_from_db()
        assert product_activo.price == Decimal('4000.00')

    def test_confirm_purga_cache_ficha(self, admin_client, product_activo, db):
        cache.set(f'product:{product_activo.pk}:detail', {'old': True}, 300)
        csv_file = _make_csv([(product_activo.sku, '4100.00')])
        preview = admin_client.post(PRICE_SYNC_URL, {'file': csv_file}, format='multipart')
        admin_client.post(
            PRICE_CONFIRM_URL,
            {'session_id': preview.json()['session_id']}, format='json'
        )
        assert cache.get(f'product:{product_activo.pk}:detail') is None

    def test_confirm_sin_session_id_retorna_400(self, admin_client, db):
        res = admin_client.post(PRICE_CONFIRM_URL, {}, format='json')
        assert res.status_code == 400

    def test_confirm_session_expirada_retorna_400(self, admin_client, db):
        res = admin_client.post(
            PRICE_CONFIRM_URL, {'session_id': 'uuid-que-no-existe'}, format='json'
        )
        assert res.status_code == 400
        # T-109-B anti-soft-on-tests (canon EN).
        assert res.json()['codigo_error'] == 'SESSION_EXPIRED'

    def test_template_descarga_csv_con_productos(
        self, admin_client, product_activo, db
    ):
        res = admin_client.get(PRICE_TMPL_URL)
        assert res.status_code == 200
        assert 'text/csv' in res['Content-Type']
        content = b''.join(res.streaming_content).decode('utf-8-sig') \
            if hasattr(res, 'streaming_content') else res.content.decode('utf-8-sig')
        assert 'sku' in content
        assert product_activo.sku in content

    def test_upload_sin_auth_retorna_401(self, api_client, db):
        csv_file = _make_csv([('X', '100')])
        res = api_client.post(PRICE_SYNC_URL, {'file': csv_file}, format='multipart')
        assert res.status_code == 401


# =============================================================================
# UC-CAT-12 — Ajuste porcentual
# =============================================================================

class TestAjustePorcentual:

    def test_ajuste_positivo_incrementa_precios(
        self, admin_client, product_activo, db
    ):
        """10% sobre 3200 = 3520."""
        res = admin_client.post(
            PRICE_SYNC_URL,
            {'mode': 'percentage', 'pct': '10'},
            format='json'
        )
        assert res.status_code == 200
        assert res.json()['valid_count'] >= 1
        preview = res.json()['preview'][0]
        assert Decimal(preview['new_price']) > Decimal(preview['old_price'])

    def test_ajuste_negativo_reduce_precios(
        self, admin_client, product_activo, db
    ):
        res = admin_client.post(
            PRICE_SYNC_URL,
            {'mode': 'percentage', 'pct': '-5'},
            format='json'
        )
        assert res.status_code == 200
        preview = res.json()['preview'][0]
        assert Decimal(preview['new_price']) < Decimal(preview['old_price'])

    def test_ajuste_pct_invalido_retorna_400(self, admin_client, db):
        res = admin_client.post(
            PRICE_SYNC_URL,
            {'mode': 'percentage', 'pct': 'abc'},
            format='json'
        )
        assert res.status_code == 400
