"""
Tests — SP-backed reports endpoints (UC-DB-RPT-01..03).

Sucesora: implementar-endpoints-db-rpt (T-114 SPLIT chica).
Cierra D-26 + D-27 + D-28 del audit T-114.

Anti-soft-on-tests (DEC-DBR-03): tests invocan los SPs reales
desplegados en practicayoruba_qa via socket Unix. NO se mockean.
"""
import pytest

pytestmark = pytest.mark.integration

BASE = '/api/v1/admin/reports/'


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

    def test_requires_admin(self, auth_client, db):
        res = auth_client.get(f'{BASE}catalog-summary/')
        assert res.status_code == 403
