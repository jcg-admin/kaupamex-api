"""
Tests — Gestión de costos (product unit cost + margin)

Feature net-new: costo unitario del producto + margen calculado.

Reglas clave:
- ``cost`` es dato sensible de negocio: SOLO el serializer/endpoint admin lo
  expone. La API pública de catálogo NUNCA debe incluir ``cost`` ni ``margin``.
- ``margin`` = price - cost; ``margin_pct`` = (price - cost) / price * 100.
  El margen usa el ``price`` base (no el precio con descuento).
- Guarda contra división por cero y costo nulo → None.
- Solo admin puede escribir ``cost``.
"""
import pytest
from decimal import Decimal
from apps.modules.catalogue.models import Category, Product
from apps.modules.catalogue.serializers import (
    ProductAdminSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
)

pytestmark = pytest.mark.integration

CATALOGUE_URL  = '/api/v2/products/'
ADMIN_PROD_URL = '/api/v2/admin/products/'


@pytest.fixture
def cat_inciensos(db):
    return Category.objects.create(name='Inciensos', slug='inciensos', is_active=True)


@pytest.fixture
def product_with_cost(db, cat_inciensos):
    _p = Product.objects.create(
        name='Incienso Oshun', slug='incienso-oshun', sku='INC-OSH-001',
        description='Incienso sagrado de Oshun',
        price=Decimal('100.00'), cost=Decimal('60.00'), stock=20,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_inciensos)
    return _p


@pytest.fixture
def product_no_cost(db, cat_inciensos):
    _p = Product.objects.create(
        name='Vela Yemaya', slug='vela-yemaya', sku='VEL-YEM-001',
        description='Vela ritual',
        price=Decimal('50.00'), stock=10,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_inciensos)
    return _p


# =============================================================================
# Modelo — persistencia y propiedades calculadas
# =============================================================================

class TestCostModel:

    def test_cost_persists(self, product_with_cost, db):
        product_with_cost.refresh_from_db()
        assert product_with_cost.cost == Decimal('60.00')

    def test_cost_nullable(self, product_no_cost, db):
        product_no_cost.refresh_from_db()
        assert product_no_cost.cost is None

    def test_margin_computed(self, product_with_cost, db):
        assert product_with_cost.margin == Decimal('40.00')

    def test_margin_pct_computed(self, product_with_cost, db):
        # (100 - 60) / 100 * 100 = 40.0
        assert product_with_cost.margin_pct == Decimal('40.00')

    def test_margin_none_when_cost_null(self, product_no_cost, db):
        assert product_no_cost.margin is None
        assert product_no_cost.margin_pct is None

    def test_margin_pct_guards_zero_price(self, db, cat_inciensos):
        p = Product.objects.create(
            name='Gratis', slug='gratis-pct', sku='FREE-001',
            description='', price=Decimal('0.00'), cost=Decimal('0.00'),
            stock=1, is_active=True, is_published=True,
        )
        p.categories.add(cat_inciensos)
        assert p.margin_pct is None


# =============================================================================
# Admin serializer — expone cost + margin
# =============================================================================

class TestAdminSerializerExposesCost:

    def test_admin_serializer_includes_cost_and_margin(self, product_with_cost, db):
        data = ProductAdminSerializer(product_with_cost).data
        assert 'cost' in data
        assert 'margin' in data
        assert 'margin_pct' in data
        assert Decimal(str(data['cost'])) == Decimal('60.00')
        assert Decimal(str(data['margin'])) == Decimal('40.00')

    def test_admin_can_set_cost(self, admin_client, product_with_cost, db):
        res = admin_client.patch(
            f'{ADMIN_PROD_URL}{product_with_cost.id}/',
            {'cost': '70.00'}, format='json',
        )
        assert res.status_code == 200, res.content
        product_with_cost.refresh_from_db()
        assert product_with_cost.cost == Decimal('70.00')

    def test_admin_negative_cost_rejected(self, admin_client, product_with_cost, db):
        res = admin_client.patch(
            f'{ADMIN_PROD_URL}{product_with_cost.id}/',
            {'cost': '-5.00'}, format='json',
        )
        assert res.status_code == 400, res.content


# =============================================================================
# CRITICAL — la API pública NUNCA expone cost ni margin
# =============================================================================

class TestPublicApiHidesCost:

    def test_public_detail_serializer_omits_cost(self, product_with_cost, db):
        data = ProductDetailSerializer(product_with_cost).data
        assert 'cost' not in data
        assert 'margin' not in data
        assert 'margin_pct' not in data

    def test_public_list_serializer_omits_cost(self, product_with_cost, db):
        data = ProductListSerializer(product_with_cost).data
        assert 'cost' not in data
        assert 'margin' not in data

    def test_public_detail_endpoint_omits_cost(self, api_client, product_with_cost, db):
        res = api_client.get(f'{CATALOGUE_URL}{product_with_cost.slug}/')
        assert res.status_code == 200
        body = res.json()
        assert 'cost' not in body
        assert 'margin' not in body
        assert 'margin_pct' not in body

    def test_non_admin_cannot_set_cost(self, auth_client, product_with_cost, db):
        res = auth_client.patch(
            f'{ADMIN_PROD_URL}{product_with_cost.id}/',
            {'cost': '1.00'}, format='json',
        )
        assert res.status_code in (401, 403), res.content
        product_with_cost.refresh_from_db()
        assert product_with_cost.cost == Decimal('60.00')
