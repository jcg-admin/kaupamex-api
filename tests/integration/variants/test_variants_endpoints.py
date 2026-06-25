"""
Tests — Variants endpoints consumed by UI UC-CHT-01..04.

UC-CHT-01: Product detail exposes variants[].
UC-CHT-02: POST /api/v2/cart/items/ accepts variant_id and maps the
           three contract error codes (VARIANTE_REQUERIDA 400,
           VARIANTE_SIN_STOCK 409, VARIANTE_NO_DISPONIBLE 404).
UC-CHT-03: Admin list/create/toggle variants under
           /api/v2/admin/products/<id>/variants/.
UC-CHT-04: Set/clear differentiated price on
           /api/v2/admin/variants/<id>/price/.
"""
import pytest
from decimal import Decimal
from apps.catalogue.models import Category, Product
from apps.chartsize.models import VariantType, VariantOption, ProductVariant

pytestmark = pytest.mark.integration

CATALOGUE_URL  = '/api/v2/products/'
CART_ITEMS_URL = '/api/v2/cart/items/'
ADMIN_PROD_URL = '/api/v2/admin/products/'
ADMIN_VAR_URL  = '/api/v2/admin/variants/'


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cat_v(db):
    return Category.objects.create(name='Variants Cat', slug='variants-cat', is_active=True)


@pytest.fixture
def product_v(db, cat_v):
    _p = Product.objects.create(
        name='Yemaya Sopera', slug='yemaya-sopera-v', sku='V-YEM-001',
        description='Orisha sopera',
        price=Decimal('2000.00'), stock=0,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_v)
    return _p


@pytest.fixture
def variant_type_v(db, product_v):
    return VariantType.objects.create(
        product=product_v, name='Orisha', is_active=True, order=0
    )


@pytest.fixture
def option_v(db, variant_type_v):
    return VariantOption.objects.create(
        variant_type=variant_type_v, label='Yemaya', slug='yemaya-v', order=0, is_active=True,
    )


@pytest.fixture
def option_v_b(db, variant_type_v):
    return VariantOption.objects.create(
        variant_type=variant_type_v, label='Oshun', slug='oshun-v', order=1, is_active=True,
    )


@pytest.fixture
def variant_v(db, product_v, option_v):
    return ProductVariant.objects.create(
        product=product_v, option=option_v,
        sku_suffix='YEM', stock=5, is_active=True,
    )


@pytest.fixture
def variant_v_sin_stock(db, product_v, option_v_b):
    return ProductVariant.objects.create(
        product=product_v, option=option_v_b,
        sku_suffix='OSH', stock=0, is_active=True,
    )


# ---------------------------------------------------------------------------
# UC-CHT-01 — Product detail exposes variants
# ---------------------------------------------------------------------------

class TestProductDetailExposesVariants:

    def test_detail_includes_variants_array(
        self, api_client, product_v, variant_v, db
    ):
        res = api_client.get(f'{CATALOGUE_URL}{product_v.slug}/')
        assert res.status_code == 200
        body = res.json()
        assert 'variants' in body
        assert isinstance(body['variants'], list)
        assert any(v['id'] == variant_v.pk for v in body['variants'])

    def test_variant_payload_uses_english_keys(
        self, api_client, product_v, variant_v, db
    ):
        res = api_client.get(f'{CATALOGUE_URL}{product_v.slug}/')
        v = next(x for x in res.json()['variants'] if x['id'] == variant_v.pk)
        for key in ('id', 'label', 'stock', 'is_available', 'effective_price'):
            assert key in v


# ---------------------------------------------------------------------------
# UC-CHT-02 — Cart add-item error contract
# ---------------------------------------------------------------------------

class TestCartAddItemVariantErrors:

    def test_missing_variant_id_returns_400_variante_requerida(
        self, api_client, product_v, variant_v, db
    ):
        res = api_client.post(CART_ITEMS_URL, {
            'product_id': product_v.pk, 'quantity': 1,
        }, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'VARIANT_REQUIRED'

    def test_inactive_variant_returns_404_variante_no_disponible(
        self, api_client, product_v, variant_v, db
    ):
        variant_v.is_active = False
        variant_v.save(update_fields=['is_active'])
        res = api_client.post(CART_ITEMS_URL, {
            'product_id': product_v.pk,
            'variant_id': variant_v.pk,
            'quantity': 1,
        }, format='json')
        assert res.status_code == 404
        assert res.json()['codigo_error'] == 'VARIANT_UNAVAILABLE'

    def test_unknown_variant_returns_404_variante_no_disponible(
        self, api_client, product_v, variant_v, db
    ):
        res = api_client.post(CART_ITEMS_URL, {
            'product_id': product_v.pk,
            'variant_id': 9999999,
            'quantity': 1,
        }, format='json')
        assert res.status_code == 404
        assert res.json()['codigo_error'] == 'VARIANT_UNAVAILABLE'

    def test_variant_without_stock_returns_409_variante_sin_stock(
        self, api_client, product_v, variant_v_sin_stock, db
    ):
        res = api_client.post(CART_ITEMS_URL, {
            'product_id': product_v.pk,
            'variant_id': variant_v_sin_stock.pk,
            'quantity': 1,
        }, format='json')
        assert res.status_code == 409
        assert res.json()['codigo_error'] == 'VARIANT_OUT_OF_STOCK'

    def test_variant_quantity_exceeds_stock_returns_409(
        self, api_client, product_v, variant_v, db
    ):
        res = api_client.post(CART_ITEMS_URL, {
            'product_id': product_v.pk,
            'variant_id': variant_v.pk,
            'quantity': variant_v.stock + 1,
        }, format='json')
        assert res.status_code == 409
        assert res.json()['codigo_error'] == 'VARIANT_OUT_OF_STOCK'


# ---------------------------------------------------------------------------
# UC-CHT-03 — Admin variants list/create/toggle
# ---------------------------------------------------------------------------

class TestAdminVariantsCrud:

    def test_list_requires_admin(
        self, api_client, auth_client, product_v, variant_v, db
    ):
        res = api_client.get(f'{ADMIN_PROD_URL}{product_v.pk}/variants/')
        assert res.status_code in (401, 403)
        res2 = auth_client.get(f'{ADMIN_PROD_URL}{product_v.pk}/variants/')
        assert res2.status_code == 403

    def test_admin_can_list_variants(
        self, admin_client, product_v, variant_v, db
    ):
        res = admin_client.get(f'{ADMIN_PROD_URL}{product_v.pk}/variants/')
        assert res.status_code == 200

    def test_admin_can_toggle_is_active(
        self, admin_client, product_v, variant_v, db
    ):
        res = admin_client.patch(
            f'{ADMIN_PROD_URL}{product_v.pk}/variants/{variant_v.pk}/',
            {'is_active': False}, format='json',
        )
        assert res.status_code == 200
        variant_v.refresh_from_db()
        assert variant_v.is_active is False


# ---------------------------------------------------------------------------
# UC-CHT-04 — Admin variant differentiated price endpoint
# ---------------------------------------------------------------------------

class TestAdminVariantPriceEndpoint:

    def test_put_price_requires_admin(
        self, api_client, auth_client, variant_v, db
    ):
        res = api_client.put(
            f'{ADMIN_VAR_URL}{variant_v.pk}/price/',
            {'price': '2500.00'}, format='json',
        )
        assert res.status_code in (401, 403)
        res2 = auth_client.put(
            f'{ADMIN_VAR_URL}{variant_v.pk}/price/',
            {'price': '2500.00'}, format='json',
        )
        assert res2.status_code == 403

    def test_put_price_sets_price_override(
        self, admin_client, product_v, variant_v, db
    ):
        res = admin_client.put(
            f'{ADMIN_VAR_URL}{variant_v.pk}/price/',
            {'price': '2500.00'}, format='json',
        )
        assert res.status_code == 200
        body = res.json()
        assert body['id'] == variant_v.pk
        assert Decimal(body['price_override']) == Decimal('2500.00')
        variant_v.refresh_from_db()
        assert variant_v.price_override == Decimal('2500.00')

    def test_put_price_rejects_non_positive(
        self, admin_client, variant_v, db
    ):
        res = admin_client.put(
            f'{ADMIN_VAR_URL}{variant_v.pk}/price/',
            {'price': '0.00'}, format='json',
        )
        assert res.status_code == 400

    def test_put_price_rejects_missing_field(
        self, admin_client, variant_v, db
    ):
        res = admin_client.put(
            f'{ADMIN_VAR_URL}{variant_v.pk}/price/',
            {}, format='json',
        )
        assert res.status_code == 400

    def test_delete_price_clears_override(
        self, admin_client, product_v, variant_v, db
    ):
        variant_v.price_override = Decimal('2900.00')
        variant_v.save(update_fields=['price_override'])
        res = admin_client.delete(f'{ADMIN_VAR_URL}{variant_v.pk}/price/')
        assert res.status_code == 200
        variant_v.refresh_from_db()
        assert variant_v.price_override is None

    def test_delete_price_when_unset_is_idempotent(
        self, admin_client, variant_v, db
    ):
        assert variant_v.price_override is None
        res = admin_client.delete(f'{ADMIN_VAR_URL}{variant_v.pk}/price/')
        assert res.status_code == 200

    def test_price_endpoint_404_for_unknown_variant(self, admin_client, db):
        res = admin_client.put(
            f'{ADMIN_VAR_URL}9999999/price/',
            {'price': '100.00'}, format='json',
        )
        assert res.status_code == 404
