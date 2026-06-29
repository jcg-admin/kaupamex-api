"""
Integration tests — P-17 catalogue browse + search + price-sync endpoints.

These complement existing catalogue tests by hitting the new URL surface
required by the UI:

  GET  /api/v2/products/<slug>/related/
  GET  /api/v2/categories/
  GET  /api/v2/products/search/?q=&category=&price_min=&price_max=&page=
  POST /api/v2/admin/price-syncs/   (type+mode dispatch)
  GET  /api/v2/admin/price-syncs/template.csv
"""
import io
from decimal import Decimal
from apps.catalogue.models import Category, Product, SearchHistory
from django.core.files.uploadedfile import SimpleUploadedFile

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def cat_browse(db):
    return Category.objects.create(
        name='Browse', slug='browse', is_active=True,
    )


@pytest.fixture
def prod_browse(db, cat_browse):
    _p = Product.objects.create(
        name='Yoruba Sample', slug='yoruba-sample', sku='BR-001',
        price=Decimal('100'), stock=5,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_browse)
    return _p


class TestRelatedProducts:

    def test_related_misma_categoria(self, api_client, cat_browse, prod_browse, db):
        p2 = Product.objects.create(
            name='Otro', slug='otro-yoruba', sku='BR-002',
            price=Decimal('100'), stock=1,
            is_active=True, is_published=True,
        )
        p2.categories.add(cat_browse)
        p2.categories.add(cat_browse)
        r = api_client.get(f'/api/v2/products/{prod_browse.slug}/related/')
        assert r.status_code == 200
        data = r.json()
        slugs = {p['slug'] for p in data['results']}
        assert p2.slug in slugs
        assert prod_browse.slug not in slugs

    def test_slug_inexistente_loud_404(self, api_client, db):
        r = api_client.get('/api/v2/products/no-existe/related/')
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'PRODUCT_NOT_FOUND'


class TestCategoryTree:

    def test_categorias_publicas(self, api_client, cat_browse, prod_browse, db):
        r = api_client.get('/api/v2/categories/')
        assert r.status_code == 200
        slugs = {c['slug'] for c in r.json()}
        assert 'browse' in slugs


class TestCatalogueSearchWrapper:

    def test_search_devuelve_normalized_query(
        self, api_client, prod_browse, db,
    ):
        r = api_client.get('/api/v2/products/?q=  Yoruba  Sample  ')
        assert r.status_code == 200
        body = r.json()
        assert body['normalized_query'] == 'Yoruba Sample'

    def test_search_persiste_history_para_auth(
        self, auth_client, user, prod_browse, db,
    ):
        r = auth_client.get('/api/v2/products/?q=yoruba')
        assert r.status_code == 200
        assert SearchHistory.objects.filter(user=user, term='yoruba').exists()


class TestPriceSyncAliases:

    def test_template_csv(self, admin_client, prod_browse, db):
        r = admin_client.get('/api/v2/admin/price-syncs/template.csv')
        assert r.status_code == 200
        assert r['Content-Type'].startswith('text/csv')
        body = r.content.decode('utf-8-sig')
        assert 'sku' in body and 'price' in body

    def test_preview_percentage_y_apply(self, admin_client, prod_browse, db):
        r = admin_client.post(
            '/api/v2/admin/price-syncs/',
            {'type': 'preview', 'mode': 'percentage', 'pct': 10}, format='json',
        )
        assert r.status_code == 200
        data = r.json()
        assert data['valid_count'] >= 1
        sid = data['session_id']

        r2 = admin_client.post(
            '/api/v2/admin/price-syncs/',
            {'type': 'apply', 'mode': 'percentage', 'session_id': sid}, format='json',
        )
        assert r2.status_code == 200
        assert r2.json()['updated_count'] >= 1

    def test_preview_csv_y_apply(self, admin_client, prod_browse, db):
        csv = 'sku,price\nBR-001,150.00\n'
        upload = SimpleUploadedFile(
            'p.csv', csv.encode('utf-8'), content_type='text/csv',
        )
        r = admin_client.post(
            '/api/v2/admin/price-syncs/',
            {'file': upload, 'type': 'preview', 'mode': 'csv'}, format='multipart',
        )
        assert r.status_code == 200
        data = r.json()
        assert data['valid_count'] == 1
        sid = data['session_id']

        r2 = admin_client.post(
            '/api/v2/admin/price-syncs/',
            {'session_id': sid, 'type': 'apply', 'mode': 'csv'}, format='json',
        )
        assert r2.status_code == 200
        prod_browse.refresh_from_db()
        assert prod_browse.price == Decimal('150.00')

    def test_apply_sesion_expirada_loud(self, admin_client, db):
        r = admin_client.post(
            '/api/v2/admin/price-syncs/',
            {'type': 'apply', 'mode': 'csv', 'session_id': 'ghost'}, format='json',
        )
        assert r.status_code == 400
        # T-109-B anti-soft-on-tests (canon EN).
        assert r.json()['codigo_error'] == 'SESSION_EXPIRED'

    def test_preview_csv_requires_file(self, admin_client, db):
        r = admin_client.post(
            '/api/v2/admin/price-syncs/',
            {'type': 'preview', 'mode': 'csv'}, format='multipart',
        )
        assert r.status_code == 400
        # T-109-B anti-soft-on-tests (canon EN).
        assert r.json()['codigo_error'] == 'CSV_REQUIRED'

    def test_anon_recibe_401(self, api_client, db):
        r = api_client.get('/api/v2/admin/price-syncs/template.csv')
        assert r.status_code == 401
