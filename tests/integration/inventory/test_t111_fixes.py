"""
Tests — T-111 fixes: admin-inventory-dashboard gaps

UC-INV-04: stock_before + reason audit fields; DESCONTINUADO filter removed.
UC-INV-02: checkout reference populated in StockMovement.
UC-INV-01: threshold field in dashboard items (API side).
"""
import pytest
from decimal import Decimal
from apps.catalogue.models import Category, Product
from apps.chartsize.models import VariantType, VariantOption, ProductVariant
from apps.inventory.models import StockMovement
from apps.inventory.services import InventoryService

pytestmark = pytest.mark.integration

INV_VARIANT_ADJUST_URL = '/api/v1/admin/inventory/variants/{pk}/adjust/'
INV_PRODUCT_ADJUST_URL = '/api/v1/admin/inventory/{pk}/adjust/'


@pytest.fixture
def cat(db):
    return Category.objects.create(name='Cat T111', slug='cat-t111', is_active=True)


@pytest.fixture
def active_product(db, cat):
    return Product.objects.create(
        name='Prod Activo', slug='prod-activo-t111', sku='T111-ACT',
        description='', category=cat,
        price=Decimal('100.00'), stock=20,
        is_active=True, is_published=True,
    )


@pytest.fixture
def inactive_product(db, cat):
    return Product.objects.create(
        name='Prod DESCONTINUADO', slug='prod-desc-t111', sku='T111-DESC',
        description='', category=cat,
        price=Decimal('100.00'), stock=5,
        is_active=False, is_published=False,
    )


@pytest.fixture
def vtype(db, active_product):
    return VariantType.objects.create(product=active_product, name='Talla', order=0)


@pytest.fixture
def vopt(db, vtype):
    return VariantOption.objects.create(variant_type=vtype, label='M', slug='m-t111', order=0)


@pytest.fixture
def active_variant(db, active_product, vopt):
    return ProductVariant.objects.create(
        product=active_product, option=vopt,
        sku_suffix='M', stock=10, is_active=True,
    )


@pytest.fixture
def inactive_variant(db, active_product, vopt):
    return ProductVariant.objects.create(
        product=active_product, option=vopt,
        sku_suffix='DESC', stock=3, is_active=False,
    )


# =============================================================================
# UC-INV-04: stock_before populated in StockMovement
# =============================================================================

class TestStockBefore:

    def test_decrement_registra_stock_before(self, active_product, db):
        active_product.stock = 15
        active_product.save()
        InventoryService.decrement(
            [{'product': active_product, 'variant': None, 'quantity': 4}],
        )
        mov = StockMovement.objects.filter(
            product=active_product, movement_type=StockMovement.TYPE_SALE,
        ).latest('created_at')
        assert mov.stock_before == 15
        assert mov.stock_after == 11

    def test_restore_registra_stock_before(self, active_product, db):
        active_product.stock = 8
        active_product.save()
        InventoryService.restore(
            [{'product': active_product, 'variant': None, 'quantity': 3}],
            reference='REF-T111',
        )
        mov = StockMovement.objects.filter(
            product=active_product, movement_type=StockMovement.TYPE_CANCELLATION,
        ).latest('created_at')
        assert mov.stock_before == 8
        assert mov.stock_after == 11

    def test_adjust_registra_stock_before(self, active_product, db):
        active_product.stock = 20
        active_product.save()
        mov = InventoryService.adjust(
            product=active_product, variant=None,
            delta=-5, notes='ajuste test', reason='MERMA',
        )
        assert mov.stock_before == 20
        assert mov.stock_after == 15

    def test_adjust_guarda_reason_estructurado(self, active_product, db):
        mov = InventoryService.adjust(
            product=active_product, variant=None,
            delta=2, reason='CONTEO_FISICO',
        )
        assert mov.reason == 'CONTEO_FISICO'

    def test_adjust_reason_en_respuesta_api(self, admin_client, active_product, db):
        url = INV_PRODUCT_ADJUST_URL.format(pk=active_product.pk)
        resp = admin_client.post(url, {'delta': 1, 'reason': 'CONTEO_FISICO', 'notes': 'api test'}, format='json')
        assert resp.status_code == 201
        assert 'stock_before' in resp.data
        assert 'reason' in resp.data

    def test_adjust_variante_stock_before_correcto(self, active_variant, active_product, db):
        active_variant.stock = 7
        active_variant.save()
        mov = InventoryService.adjust(
            product=active_product, variant=active_variant,
            delta=-2, reason='ROBO',
        )
        assert mov.stock_before == 7
        assert mov.stock_after == 5
        assert mov.reason == 'ROBO'


# =============================================================================
# UC-INV-04: DESCONTINUADO — is_active filter removed
# =============================================================================

class TestDescontinuadoAjuste:

    def test_ajuste_producto_inactivo_permitido(
        self, admin_client, inactive_product, db
    ):
        url = INV_PRODUCT_ADJUST_URL.format(pk=inactive_product.pk)
        resp = admin_client.post(
            url, {'delta': -2, 'reason': 'DESCONTINUADO', 'notes': 'ajuste DESCONTINUADO'}, format='json'
        )
        assert resp.status_code == 201
        inactive_product.refresh_from_db()
        assert inactive_product.stock == 3

    def test_ajuste_variante_inactiva_permitido(
        self, admin_client, inactive_variant, active_product, db
    ):
        url = INV_VARIANT_ADJUST_URL.format(pk=inactive_variant.pk)
        resp = admin_client.post(
            url,
            {'new_quantity': 1, 'reason': 'DESCONTINUADO', 'observations': ''},
            format='json',
        )
        assert resp.status_code == 201
        inactive_variant.refresh_from_db()
        assert inactive_variant.stock == 1


# =============================================================================
# UC-INV-02 F-02: checkout reference en StockMovement
# =============================================================================

class TestCheckoutReference:

    def test_decrement_con_reference_guarda_order_number(self, active_product, db):
        InventoryService.decrement(
            [{'product': active_product, 'variant': None, 'quantity': 1}],
            reference='PY-ABCD1234',
        )
        mov = StockMovement.objects.filter(
            product=active_product, movement_type=StockMovement.TYPE_SALE,
        ).latest('created_at')
        assert mov.reference == 'PY-ABCD1234'
