"""
Tests de integracion — ProductDetailSerializer DEC-BC-17
T-408 (parcial): sub-items 17a (discount) + 17b (images).
Sub-items 17c (reviews_summary/questions_count) y 17d (price_breakdown IVA)
pendientes de implementacion.
"""
import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from apps.catalogue.models import Category, Product, ProductDiscount

pytestmark = pytest.mark.integration

DETAIL_URL = '/api/v1/catalogue/{slug}/'


@pytest.fixture
def cat_det(db):
    return Category.objects.create(name='Orishas Detail', slug='orishas-detail', is_active=True)


@pytest.fixture
def prod_det(cat_det, db):
    return Product.objects.create(
        name='Collar Yemaya Detail',
        slug='collar-yemaya-detail',
        sku='DET-001',
        category=cat_det,
        price=Decimal('500.00'),
        stock=3,
        is_active=True,
        is_published=True,
    )


class TestProductDetailSerializerDEC17:
    """T-408: sub-items 17a + 17b de DEC-BC-17."""

    def _get_detail(self, api_client, prod):
        r = api_client.get(DETAIL_URL.format(slug=prod.slug))
        assert r.status_code == 200
        return r.json()

    # --- Sub-item 17a: discount field ---

    def test_discount_null_sin_descuento(self, api_client, prod_det):
        data = self._get_detail(api_client, prod_det)
        assert 'discount' in data
        assert data['discount'] is None

    def test_discount_presente_con_descuento_vigente(self, api_client, prod_det):
        ProductDiscount.objects.create(
            product=prod_det,
            discount_pct=Decimal('25.00'),
            valid_from=timezone.now() - timedelta(hours=1),
            valid_until=timezone.now() + timedelta(days=7),
            is_active=True,
        )
        data = self._get_detail(api_client, prod_det)
        assert data['discount'] is not None
        assert data['discount']['pct'] == pytest.approx(25.0)
        assert 'discounted_price' in data['discount']
        assert data['discount']['discounted_price'] == pytest.approx(375.0, rel=1e-2)

    def test_discount_null_con_descuento_expirado(self, api_client, prod_det):
        ProductDiscount.objects.create(
            product=prod_det,
            discount_pct=Decimal('10.00'),
            valid_from=timezone.now() - timedelta(days=10),
            valid_until=timezone.now() - timedelta(days=1),
            is_active=True,
        )
        data = self._get_detail(api_client, prod_det)
        assert data['discount'] is None

    # --- Sub-item 17b: images field ---

    def test_images_lista_vacia_sin_imagenes(self, api_client, prod_det):
        data = self._get_detail(api_client, prod_det)
        assert 'images' in data
        assert data['images'] == []
