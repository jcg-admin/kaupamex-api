"""
Tests de integracion — API v2 F4: inventory admin + catalogue admin

Verifica los endpoints /api/v2/admin/ para el bloque F4:
  - inventory: imports (Tier A), product/variant adjust (Tier B),
               restocks (Tier A rename), alert status (Tier B)
  - catalogue admin: products/imports (Tier B), price-syncs (Tier B),
                     product-discount status (Tier B)

F7 eliminó las rutas v1-compat; este archivo verifica solo v2 canónico.
"""
import pytest

pytestmark = pytest.mark.integration

# ─── URLs v2 ────────────────────────────────────────────────────────────────
V2_INVENTORY_BASE        = '/api/v2/admin/inventory/'
V2_CATALOGUE_ADMIN_BASE  = '/api/v2/admin/'


# ─── Inventory — Tier A: imports ─────────────────────────────────────────────

class TestInventoryImportsV2:
    def test_unauthenticated_returns_401(self, api_client):
        r = api_client.post(V2_INVENTORY_BASE + 'imports/', {})
        assert r.status_code == 401

    def test_non_admin_returns_403(self, auth_client):
        r = auth_client.post(V2_INVENTORY_BASE + 'imports/', {})
        assert r.status_code == 403


class TestInventoryImportStatusV2:
    def test_unauthenticated_returns_401(self, api_client):
        r = api_client.get(V2_INVENTORY_BASE + 'imports/job-abc123/')
        assert r.status_code == 401


class TestInventoryZeroStockV2:
    def test_unauthenticated_returns_401(self, api_client):
        r = api_client.get(V2_INVENTORY_BASE + 'variants/1/zero-stock/')
        assert r.status_code == 401


# ─── Inventory — Tier B: product adjust ──────────────────────────────────────

class TestInventoryProductAdjustV2:
    def test_unauthenticated_returns_401(self, api_client):
        r = api_client.patch(
            V2_INVENTORY_BASE + '1/', {}, content_type='application/json'
        )
        assert r.status_code == 401

    def test_non_admin_returns_403(self, auth_client):
        r = auth_client.patch(
            V2_INVENTORY_BASE + '1/', {}, content_type='application/json'
        )
        assert r.status_code == 403


# ─── Inventory — Tier B: variant adjust ──────────────────────────────────────

class TestInventoryVariantAdjustV2:
    def test_unauthenticated_returns_401(self, api_client):
        r = api_client.patch(
            V2_INVENTORY_BASE + 'variants/1/', {}, content_type='application/json'
        )
        assert r.status_code == 401

    def test_non_admin_returns_403(self, auth_client):
        r = auth_client.patch(
            V2_INVENTORY_BASE + 'variants/1/', {}, content_type='application/json'
        )
        assert r.status_code == 403


# ─── Inventory — Tier A rename: variant restocks ─────────────────────────────

class TestInventoryVariantRestocksV2:
    def test_unauthenticated_returns_401(self, api_client):
        r = api_client.post(V2_INVENTORY_BASE + 'variants/1/restocks/', {})
        assert r.status_code == 401

    def test_non_admin_returns_403(self, auth_client):
        r = auth_client.post(V2_INVENTORY_BASE + 'variants/1/restocks/', {})
        assert r.status_code == 403


# ─── Inventory — Tier B: alert status ────────────────────────────────────────

class TestInventoryAlertStatusV2:
    def test_unauthenticated_returns_401(self, api_client):
        r = api_client.patch(
            V2_INVENTORY_BASE + 'alerts/1/',
            {'action': 'resolve'},
            content_type='application/json',
        )
        assert r.status_code == 401

    def test_non_admin_returns_403(self, auth_client):
        r = auth_client.patch(
            V2_INVENTORY_BASE + 'alerts/1/',
            {'action': 'resolve'},
            content_type='application/json',
        )
        assert r.status_code == 403

    def test_invalid_action_returns_400(self, admin_auth_client):
        r = admin_auth_client.patch(
            V2_INVENTORY_BASE + 'alerts/999/',
            {'action': 'delete'},
            content_type='application/json',
        )
        assert r.status_code == 400
        assert r.data['codigo_error'] == 'INVALID_ACTION'


# ─── Catalogue admin — Tier B: catalogue imports ─────────────────────────────

class TestCatalogueImportsV2:
    def test_unauthenticated_returns_401(self, api_client):
        r = api_client.post(V2_CATALOGUE_ADMIN_BASE + 'products/imports/', {})
        assert r.status_code == 401

    def test_non_admin_returns_403(self, auth_client):
        r = auth_client.post(V2_CATALOGUE_ADMIN_BASE + 'products/imports/', {})
        assert r.status_code == 403


# ─── Catalogue admin — Tier B: price-syncs (canonical v2) ───────────────────

class TestProductPriceSyncsV2:
    def test_unauthenticated_returns_401(self, api_client):
        r = api_client.post(
            V2_CATALOGUE_ADMIN_BASE + 'price-syncs/', {},
            content_type='application/json',
        )
        assert r.status_code == 401

    def test_non_admin_returns_403(self, auth_client):
        r = auth_client.post(
            V2_CATALOGUE_ADMIN_BASE + 'price-syncs/', {},
            content_type='application/json',
        )
        assert r.status_code == 403


# ─── Catalogue admin — Tier B: product-discount status ───────────────────────

class TestProductDiscountStatusV2:
    def test_unauthenticated_returns_401(self, api_client):
        r = api_client.patch(
            V2_CATALOGUE_ADMIN_BASE + 'product-discounts/1/',
            {'active': False},
            content_type='application/json',
        )
        assert r.status_code == 401

    def test_non_admin_returns_403(self, auth_client):
        r = auth_client.patch(
            V2_CATALOGUE_ADMIN_BASE + 'product-discounts/1/',
            {'active': False},
            content_type='application/json',
        )
        assert r.status_code == 403

    def test_invalid_action_returns_400(self, admin_auth_client):
        r = admin_auth_client.patch(
            V2_CATALOGUE_ADMIN_BASE + 'product-discounts/999/',
            {'active': True},
            content_type='application/json',
        )
        assert r.status_code == 400
        assert r.data['codigo_error'] == 'INVALID_ACTION'


# ─── Catalogue admin — Tier B: price-syncs (browse, consolidated) ────────────

class TestPriceSyncsV2:
    def test_unauthenticated_returns_401(self, api_client):
        r = api_client.post(
            V2_CATALOGUE_ADMIN_BASE + 'price-syncs/', {},
            content_type='application/json',
        )
        assert r.status_code == 401

    def test_non_admin_returns_403(self, auth_client):
        r = auth_client.post(
            V2_CATALOGUE_ADMIN_BASE + 'price-syncs/', {},
            content_type='application/json',
        )
        assert r.status_code == 403

    def test_invalid_type_mode_returns_400(self, admin_auth_client):
        r = admin_auth_client.post(
            V2_CATALOGUE_ADMIN_BASE + 'price-syncs/',
            {'type': 'delete', 'mode': 'csv'},
            content_type='application/json',
        )
        assert r.status_code == 400
        assert r.data['codigo_error'] == 'INVALID_ACTION'


# ─── Catalogue admin — Tier A: price-syncs template ──────────────────────────

class TestPriceSyncsTemplateV2:
    def test_unauthenticated_returns_401(self, api_client):
        r = api_client.get(V2_CATALOGUE_ADMIN_BASE + 'price-syncs/template.csv')
        assert r.status_code == 401
