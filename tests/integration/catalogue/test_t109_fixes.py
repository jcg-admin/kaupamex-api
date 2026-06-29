"""
Tests — T-109 fixes: admin-catalogue-management gaps

UC-CAT-09: SKU duplicado retorna 409 CONFLICT (DuplicateSKUError).
UC-CAT-10 RNF 6.3: ProductPriceHistory creado en PATCH y CSV sync.
"""
import pytest
from decimal import Decimal
from apps.catalogue.models import Category, Product, ProductPriceHistory

pytestmark = pytest.mark.integration

ADMIN_PROD_URL = '/api/v2/admin/products/'
PRICE_SYNC_URL = '/api/v2/admin/price-syncs/'
PRICE_SYNC_CONFIRM_URL = '/api/v2/admin/price-syncs/'


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def cat(db):
    return Category.objects.create(name='Cat T109', slug='cat-t109', is_active=True)


@pytest.fixture
def product_a(db, cat):
    _p = Product.objects.create(
        name='Producto A', slug='producto-a-t109', sku='T109-A',
        description='',
        price=Decimal('100.00'), stock=5,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat)
    return _p


@pytest.fixture
def product_b(db, cat):
    _p = Product.objects.create(
        name='Producto B', slug='producto-b-t109', sku='T109-B',
        description='',
        price=Decimal('200.00'), stock=3,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat)
    return _p


# =============================================================================
# UC-CAT-09: SKU duplicado → 409 CONFLICT
# =============================================================================

class TestSKUDuplicado409:

    def test_crear_con_sku_duplicado_retorna_409(
        self, admin_client, cat, product_a, db
    ):
        """FR-CAT-09.02: SKU ya en uso al crear → 409 CONFLICT."""
        res = admin_client.post(ADMIN_PROD_URL, {
            'name': 'Otro', 'sku': product_a.sku,
            'category_id': cat.pk, 'base_price': '50.00',
        }, format='json')
        assert res.status_code == 409

    def test_editar_con_sku_duplicado_retorna_409(
        self, admin_client, product_a, product_b, db
    ):
        """FR-CAT-09.02: SKU ya en uso al editar → 409 CONFLICT."""
        res = admin_client.patch(
            f'{ADMIN_PROD_URL}{product_a.pk}/',
            {'sku': product_b.sku},
            format='json',
        )
        assert res.status_code == 409

    def test_editar_mismo_sku_del_propio_producto_retorna_200(
        self, admin_client, product_a, db
    ):
        """El propio SKU del producto no debe disparar duplicate check."""
        res = admin_client.patch(
            f'{ADMIN_PROD_URL}{product_a.pk}/',
            {'sku': product_a.sku},
            format='json',
        )
        assert res.status_code == 200

    def test_sku_se_guarda_en_mayusculas(self, admin_client, cat, db):
        """validate_sku() normaliza a mayúsculas."""
        res = admin_client.post(ADMIN_PROD_URL, {
            'name': 'Prueba mayus', 'sku': 't109-lower',
            'category_id': cat.pk, 'base_price': '10.00',
        }, format='json')
        assert res.status_code == 201
        assert res.json()['sku'] == 'T109-LOWER'


# =============================================================================
# UC-CAT-10 RNF 6.3: ProductPriceHistory via PATCH
# =============================================================================

class TestPriceHistoryPATCH:

    def test_patch_precio_crea_historial(
        self, admin_client, product_a, db
    ):
        """PATCH base_price → ProductPriceHistory(source=MANUAL) creado."""
        old_price = product_a.price
        admin_client.patch(
            f'{ADMIN_PROD_URL}{product_a.pk}/',
            {'base_price': '999.00'},
            format='json',
        )
        entry = ProductPriceHistory.objects.filter(product=product_a).latest('created_at')
        assert entry.old_price == old_price
        assert entry.new_price == Decimal('999.00')
        assert entry.source == ProductPriceHistory.MANUAL

    def test_patch_sin_cambio_precio_no_crea_historial(
        self, admin_client, product_a, db
    ):
        """PATCH sin cambio de precio no genera registro en historial."""
        admin_client.patch(
            f'{ADMIN_PROD_URL}{product_a.pk}/',
            {'is_published': True},
            format='json',
        )
        assert not ProductPriceHistory.objects.filter(product=product_a).exists()

    def test_price_history_endpoint_retorna_datos(
        self, admin_client, product_a, db
    ):
        """GET /admin/products/{pk}/price-history/ retorna historial paginado."""
        ProductPriceHistory.objects.create(
            product=product_a,
            old_price=Decimal('100.00'),
            new_price=Decimal('120.00'),
            source=ProductPriceHistory.MANUAL,
        )
        res = admin_client.get(f'{ADMIN_PROD_URL}{product_a.pk}/price-history/')
        assert res.status_code == 200
        data = res.json()
        assert data['count'] == 1
        assert data['results'][0]['old_price'] == '100.00'
        assert data['results'][0]['new_price'] == '120.00'
        assert data['results'][0]['source'] == 'MANUAL'
