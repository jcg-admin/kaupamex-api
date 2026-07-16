"""
Tests — Stock replenishment (entrada de stock / restock)

UC-INV (net-new): admin replenishes stock for a variant or product with an
optional purchase reference. Distinct from UC-INV-04 manual adjustment:
restock is always a positive entry tied to a supplier/purchase reference and
records a dedicated RESTOCK movement type.

TDD: these tests are written FIRST (RED) — the RESTOCK type, the service
method, the serializer and the endpoint do not exist yet.
"""
from decimal import Decimal

import pytest

from apps.modules.catalogue.models import Category, Product
from apps.modules.chartsize.models import VariantType, VariantOption, ProductVariant
from apps.modules.inventory.models import StockAlert, StockMovement
from apps.modules.inventory.services import InventoryService

pytestmark = pytest.mark.integration

RESTOCK_URL = '/api/v2/admin/inventory/variants/{pk}/restocks/'


@pytest.fixture
def cat_rst(db):
    return Category.objects.create(name='Cat RST', slug='cat-rst', is_active=True)


@pytest.fixture
def product_rst(db, cat_rst):
    _p = Product.objects.create(
        name='Prod RST', slug='prod-rst', sku='RST-001',
        description='', price=Decimal('500.00'), stock=8,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_rst)
    return _p


@pytest.fixture
def variant_type_rst(db, product_rst):
    return VariantType.objects.create(product=product_rst, name='Presentacion', order=0)


@pytest.fixture
def opt_rst(db, variant_type_rst):
    return VariantOption.objects.create(
        variant_type=variant_type_rst, label='250ml', slug='250ml-rst', order=0,
    )


@pytest.fixture
def variant_rst(db, product_rst, opt_rst):
    return ProductVariant.objects.create(
        product=product_rst, option=opt_rst,
        sku_suffix='250', stock=4, is_active=True,
    )


# =============================================================================
# Service layer — InventoryService.restock()
# =============================================================================

class TestRestockService:

    def test_restock_variant_increments_stock(self, product_rst, variant_rst, admin_user, db):
        mov = InventoryService.restock(
            product=product_rst, variant=variant_rst, quantity=10,
            reference='PO-2026-001', notes='Recepcion proveedor',
            created_by=admin_user,
        )
        variant_rst.refresh_from_db()
        assert variant_rst.stock == 14
        assert mov.movement_type == StockMovement.TYPE_RESTOCK
        assert mov.delta == 10
        assert mov.stock_before == 4
        assert mov.stock_after == 14
        assert mov.reference == 'PO-2026-001'
        assert mov.notes == 'Recepcion proveedor'
        assert mov.created_by_id == admin_user.pk

    def test_restock_product_increments_stock(self, product_rst, admin_user, db):
        mov = InventoryService.restock(
            product=product_rst, variant=None, quantity=5,
            reference='PO-2026-002', created_by=admin_user,
        )
        product_rst.refresh_from_db()
        assert product_rst.stock == 13
        assert mov.delta == 5
        assert mov.movement_type == StockMovement.TYPE_RESTOCK

    def test_restock_resolves_open_alert(self, product_rst, variant_rst, admin_user, db):
        """A restock that lifts stock above threshold resolves the open alert."""
        alert = StockAlert.objects.create(
            product=product_rst, variant=variant_rst, stock_at_alert=4, resolved=False,
        )
        InventoryService.restock(
            product=product_rst, variant=variant_rst, quantity=50,
            reference='PO-2026-003', created_by=admin_user,
        )
        alert.refresh_from_db()
        assert alert.resolved is True
        assert alert.resolved_at is not None

    def test_restock_rejects_non_positive_quantity(self, product_rst, variant_rst, admin_user, db):
        with pytest.raises(ValueError):
            InventoryService.restock(
                product=product_rst, variant=variant_rst, quantity=0,
                reference='PO-BAD', created_by=admin_user,
            )
        variant_rst.refresh_from_db()
        assert variant_rst.stock == 4  # unchanged


# =============================================================================
# Endpoint — POST /api/v2/admin/inventory/variants/<pk>/restock/
# =============================================================================

class TestRestockEndpoint:

    def test_restock_increments_and_creates_movement(
        self, admin_client, admin_user, variant_rst, db
    ):
        res = admin_client.post(
            RESTOCK_URL.format(pk=variant_rst.pk),
            {'quantity': 12, 'reference': 'PO-2026-010', 'notes': 'Lote A'},
            format='json',
        )
        assert res.status_code == 201, res.content
        variant_rst.refresh_from_db()
        assert variant_rst.stock == 16
        mov = StockMovement.objects.filter(
            variant=variant_rst, movement_type=StockMovement.TYPE_RESTOCK,
        ).latest('created_at')
        assert mov.delta == 12
        assert mov.reference == 'PO-2026-010'
        assert mov.created_by_id == admin_user.pk

    def test_restock_quantity_zero_returns_400(self, admin_client, variant_rst, db):
        res = admin_client.post(
            RESTOCK_URL.format(pk=variant_rst.pk),
            {'quantity': 0, 'reference': 'PO-Z'},
            format='json',
        )
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'INVALID_QUANTITY'
        variant_rst.refresh_from_db()
        assert variant_rst.stock == 4  # unchanged

    def test_restock_quantity_negative_returns_400(self, admin_client, variant_rst, db):
        res = admin_client.post(
            RESTOCK_URL.format(pk=variant_rst.pk),
            {'quantity': -3, 'reference': 'PO-N'},
            format='json',
        )
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'INVALID_QUANTITY'

    def test_restock_unknown_variant_returns_404(self, admin_client, db):
        res = admin_client.post(
            RESTOCK_URL.format(pk=999999),
            {'quantity': 5, 'reference': 'PO-X'},
            format='json',
        )
        assert res.status_code == 404
        assert res.json()['codigo_error'] == 'VARIANT_NOT_FOUND'

    def test_restock_non_admin_returns_403(self, auth_client, variant_rst, db):
        res = auth_client.post(
            RESTOCK_URL.format(pk=variant_rst.pk),
            {'quantity': 5, 'reference': 'PO-NA'},
            format='json',
        )
        assert res.status_code == 403

    def test_restock_unauthenticated_returns_401(self, api_client, variant_rst, db):
        res = api_client.post(
            RESTOCK_URL.format(pk=variant_rst.pk),
            {'quantity': 5, 'reference': 'PO-U'},
            format='json',
        )
        assert res.status_code == 401
