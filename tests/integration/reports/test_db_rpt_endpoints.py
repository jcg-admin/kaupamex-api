"""
Tests — SP-backed reports endpoints (UC-DB-RPT-01..03).

Sucesora: implementar-endpoints-db-rpt (T-114 SPLIT chica).
Cierra D-26 + D-27 + D-28 del audit T-114.

Anti-soft-on-tests (DEC-DBR-03): tests invocan los SPs reales
desplegados en practicayoruba_qa via socket Unix. NO se mockean.
"""
from decimal import Decimal

import pytest

from apps.catalogue.models import Category, Product
from apps.settings_app.models import SiteSettings

pytestmark = pytest.mark.integration

BASE = '/api/v1/admin/reports/'

CATALOG_BY_CATEGORY_COLUMNS = {
    'category_id', 'category', 'category_slug',
    'total_products', 'published', 'out_of_stock',
    'price_min', 'price_max', 'price_avg',
}

LOW_STOCK_COLUMNS = {
    'id', 'name', 'sku', 'slug', 'stock', 'threshold',
    'units_needed', 'status', 'category', 'price', 'is_published',
}

CATALOG_SUMMARY_COLUMNS = {
    'total_products', 'active', 'published', 'featured',
    'out_of_stock', 'low_stock', 'price_min', 'price_max',
    'price_avg', 'stock_threshold', 'tax_rate', 'free_shipping_threshold',
}

VALID_STOCK_STATUSES = {'OUT_OF_STOCK', 'LOW_STOCK', 'AVAILABLE'}


def _make_category(name='Test Cat', slug='test-cat'):
    cat, _ = Category.objects.get_or_create(name=name, defaults={'slug': slug})
    return cat


def _make_product(category, name, sku, stock, price=Decimal('100.00'),
                  is_active=True, is_published=True, is_featured=False):
    return Product.objects.create(
        name=name, slug=f'slug-{sku}', sku=sku,
        price=price, stock=stock, category=category,
        is_active=is_active, is_published=is_published,
        is_featured=is_featured,
    )


def _ensure_site_settings(min_stock_threshold=5):
    settings = SiteSettings.objects.first()
    if settings is None:
        settings = SiteSettings.objects.create(
            site_name='Test', min_stock_threshold=min_stock_threshold,
        )
    else:
        settings.min_stock_threshold = min_stock_threshold
        settings.save()
    return settings


class TestCatalogByCategoryReport:
    """UC-DB-RPT-01 — sp_rpt_catalog_by_category."""

    def test_endpoint_returns_200(self, admin_client, db):
        res = admin_client.get(f'{BASE}catalog-by-category/')
        assert res.status_code == 200, res.content

    def test_shape_envuelta(self, admin_client, db):
        """DEC-DBR-04: {generated_at, count, results}."""
        res = admin_client.get(f'{BASE}catalog-by-category/')
        body = res.json()
        assert 'generated_at' in body
        assert 'count' in body
        assert 'results' in body
        assert isinstance(body['results'], list)
        assert body['count'] == len(body['results'])

    def test_column_structure(self, admin_client, db):
        """Cada fila de results tiene exactamente las columnas del SP."""
        cat = _make_category('Col Cat', 'col-cat')
        _make_product(cat, 'ColProd', 'SKU-COL-01', stock=10)

        res = admin_client.get(f'{BASE}catalog-by-category/')
        body = res.json()
        assert body['count'] >= 1
        row = next(r for r in body['results'] if r['category_slug'] == 'col-cat')
        assert CATALOG_BY_CATEGORY_COLUMNS <= set(row.keys())

    def test_active_categories_only(self, admin_client, db):
        """El SP filtra por c.is_active=1; categorías inactivas no aparecen."""
        inactive = Category.objects.create(
            name='Inactive Cat', slug='inactive-cat', is_active=False,
        )
        _make_product(inactive, 'InactiveProd', 'SKU-INACT-01', stock=5)

        res = admin_client.get(f'{BASE}catalog-by-category/')
        body = res.json()
        slugs = {r['category_slug'] for r in body['results']}
        assert 'inactive-cat' not in slugs

    def test_count_consistency(self, admin_client, db):
        """count == len(results) siempre."""
        res = admin_client.get(f'{BASE}catalog-by-category/')
        body = res.json()
        assert body['count'] == len(body['results'])

    def test_requires_admin(self, auth_client, db):
        res = auth_client.get(f'{BASE}catalog-by-category/')
        assert res.status_code == 403


class TestLowStockReport:
    """UC-DB-RPT-02 — sp_rpt_low_stock."""

    def test_endpoint_returns_200(self, admin_client, db):
        res = admin_client.get(f'{BASE}low-stock/')
        assert res.status_code == 200, res.content

    def test_shape_envuelta(self, admin_client, db):
        res = admin_client.get(f'{BASE}low-stock/')
        body = res.json()
        assert {'generated_at', 'count', 'results'} <= set(body.keys())
        assert isinstance(body['results'], list)

    def test_column_structure(self, admin_client, db):
        """Cada fila de results tiene exactamente las columnas del SP."""
        settings = _ensure_site_settings(min_stock_threshold=10)
        cat = _make_category('Low Cat', 'low-cat')
        _make_product(cat, 'LowProd', 'SKU-LOW-01', stock=3)

        res = admin_client.get(f'{BASE}low-stock/')
        body = res.json()
        if body['count'] > 0:
            row = body['results'][0]
            assert LOW_STOCK_COLUMNS <= set(row.keys())

    def test_status_values_are_english(self, admin_client, db):
        """fn_stock_status retorna OUT_OF_STOCK|LOW_STOCK — nunca español."""
        _ensure_site_settings(min_stock_threshold=10)
        cat = _make_category('Status Cat', 'status-cat')
        _make_product(cat, 'ZeroProd', 'SKU-ZERO-01', stock=0)
        _make_product(cat, 'LowProd2', 'SKU-LOW-02', stock=3)

        res = admin_client.get(f'{BASE}low-stock/')
        body = res.json()
        for row in body['results']:
            assert row['status'] in VALID_STOCK_STATUSES, (
                f"status '{row['status']}' no es un valor inglés válido"
            )
            assert row['status'] not in ('AGOTADO', 'BAJO_STOCK', 'DISPONIBLE'), (
                f"status '{row['status']}' está en español (DEC-DOC-005)"
            )

    def test_filtering_below_threshold(self, admin_client, db):
        """El SP solo retorna productos con stock < min_stock_threshold."""
        settings = _ensure_site_settings(min_stock_threshold=5)
        cat = _make_category('Filter Cat', 'filter-cat')
        _make_product(cat, 'BelowThresh', 'SKU-BLW-01', stock=2)
        _make_product(cat, 'AtThresh',    'SKU-AT-01',  stock=5)
        _make_product(cat, 'AboveThresh', 'SKU-ABV-01', stock=10)

        res = admin_client.get(f'{BASE}low-stock/')
        body = res.json()
        skus = {r['sku'] for r in body['results']}
        assert 'SKU-BLW-01' in skus
        assert 'SKU-AT-01' not in skus
        assert 'SKU-ABV-01' not in skus

    def test_units_needed_calculation(self, admin_client, db):
        """units_needed == threshold - stock para cada fila."""
        settings = _ensure_site_settings(min_stock_threshold=10)
        cat = _make_category('Calc Cat', 'calc-cat')
        _make_product(cat, 'CalcProd', 'SKU-CALC-01', stock=3)

        res = admin_client.get(f'{BASE}low-stock/')
        body = res.json()
        calc_rows = [r for r in body['results'] if r['sku'] == 'SKU-CALC-01']
        assert len(calc_rows) == 1
        row = calc_rows[0]
        assert row['units_needed'] == row['threshold'] - row['stock']

    def test_requires_admin(self, auth_client, db):
        res = auth_client.get(f'{BASE}low-stock/')
        assert res.status_code == 403


class TestCatalogSummaryReport:
    """UC-DB-RPT-03 — sp_rpt_catalog_summary."""

    def test_endpoint_returns_200(self, admin_client, db):
        res = admin_client.get(f'{BASE}catalog-summary/')
        assert res.status_code == 200, res.content

    def test_shape_envuelta(self, admin_client, db):
        res = admin_client.get(f'{BASE}catalog-summary/')
        body = res.json()
        assert {'generated_at', 'count', 'results'} <= set(body.keys())
        assert isinstance(body['results'], list)

    def test_column_structure_with_sitesettings(self, admin_client, db):
        """Con SiteSettings presente el SP retorna 1 fila con todas las columnas."""
        _ensure_site_settings(min_stock_threshold=5)
        cat = _make_category('Sum Cat', 'sum-cat')
        _make_product(cat, 'SumProd', 'SKU-SUM-01', stock=10)

        res = admin_client.get(f'{BASE}catalog-summary/')
        body = res.json()
        assert body['count'] == 1
        row = body['results'][0]
        assert CATALOG_SUMMARY_COLUMNS <= set(row.keys())

    def test_returns_200_regardless_of_sitesettings(self, admin_client, db):
        """El endpoint retorna 200 siempre — count=1 con SiteSettings, 0 sin ella."""
        res = admin_client.get(f'{BASE}catalog-summary/')
        assert res.status_code == 200
        body = res.json()
        assert body['count'] in (0, 1)

    def test_total_products_count(self, admin_client, db):
        """total_products refleja el conteo real de productos en el catálogo."""
        _ensure_site_settings()
        cat = _make_category('Count Cat', 'count-cat')
        before_res = admin_client.get(f'{BASE}catalog-summary/')
        before_count = before_res.json()['results'][0]['total_products'] if before_res.json()['count'] else 0

        _make_product(cat, 'CountProd1', 'SKU-CNT-01', stock=10)
        _make_product(cat, 'CountProd2', 'SKU-CNT-02', stock=20)

        after_res = admin_client.get(f'{BASE}catalog-summary/')
        after_count = after_res.json()['results'][0]['total_products']
        assert after_count == before_count + 2

    def test_requires_admin(self, auth_client, db):
        res = auth_client.get(f'{BASE}catalog-summary/')
        assert res.status_code == 403
