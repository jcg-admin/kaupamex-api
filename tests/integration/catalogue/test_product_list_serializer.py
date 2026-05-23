"""
Tests de integracion — ProductListSerializer DEC-BC-14
T-403: verifica que GET /api/v1/catalogue/ expone los 5 campos de DEC-BC-14:
  image, discount, variants_available, is_featured, availability.
"""
import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from apps.catalogue.models import Category, Product, ProductDiscount

pytestmark = pytest.mark.integration

CATALOGUE_URL = '/api/v1/catalogue/'


@pytest.fixture
def cat_dec14(db):
    return Category.objects.create(name='Orishas DEC14', slug='orishas-dec14', is_active=True)


@pytest.fixture
def prod_dec14(cat_dec14, db):
    return Product.objects.create(
        name='Collar Orula DEC14',
        slug='collar-orula-dec14',
        sku='DEC14-001',
        category=cat_dec14,
        price=Decimal('250.00'),
        stock=5,
        is_active=True,
        is_published=True,
        is_featured=True,
    )


class TestProductListSerializerDEC14:
    """T-403: los 5 campos DEC-BC-14 estan en la respuesta del listado de catalogo."""

    def _get_item(self, api_client, prod):
        r = api_client.get(CATALOGUE_URL)
        assert r.status_code == 200
        results = r.json().get('results', [])
        match = [i for i in results if i['id'] == prod.id]
        assert match, f'Producto {prod.id} no encontrado en respuesta'
        return match[0]

    def test_image_field_null_sin_imagenes(self, api_client, prod_dec14):
        item = self._get_item(api_client, prod_dec14)
        assert 'image' in item
        assert item['image'] is None

    def test_is_featured_field_presente(self, api_client, prod_dec14):
        item = self._get_item(api_client, prod_dec14)
        assert 'is_featured' in item
        assert item['is_featured'] is True

    def test_availability_in_stock(self, api_client, prod_dec14):
        item = self._get_item(api_client, prod_dec14)
        assert 'availability' in item
        assert item['availability'] == 'IN_STOCK'

    def test_availability_out_of_stock(self, api_client, cat_dec14, db):
        p = Product.objects.create(
            name='Sin Stock DEC14', slug='sin-stock-dec14', sku='DEC14-002',
            category=cat_dec14, price=Decimal('100.00'),
            stock=0, is_active=True, is_published=True,
        )
        r = api_client.get(CATALOGUE_URL)
        results = r.json().get('results', [])
        item = next((i for i in results if i['id'] == p.id), None)
        assert item is not None
        assert item['availability'] == 'OUT_OF_STOCK'

    def test_variants_available_false_sin_variantes(self, api_client, prod_dec14):
        item = self._get_item(api_client, prod_dec14)
        assert 'variants_available' in item
        assert item['variants_available'] is False

    def test_discount_null_sin_descuento_activo(self, api_client, prod_dec14):
        item = self._get_item(api_client, prod_dec14)
        assert 'discount' in item
        assert item['discount'] is None

    def test_discount_presente_con_descuento_vigente(self, api_client, prod_dec14):
        ProductDiscount.objects.create(
            product=prod_dec14,
            discount_pct=Decimal('20.00'),
            valid_from=timezone.now() - timedelta(hours=1),
            valid_until=timezone.now() + timedelta(days=7),
            is_active=True,
        )
        item = self._get_item(api_client, prod_dec14)
        assert item['discount'] is not None
        assert item['discount']['pct'] == pytest.approx(20.0)
        assert 'discounted_price' in item['discount']
        assert item['discount']['discounted_price'] == pytest.approx(200.0, rel=1e-2)

    def test_discount_null_con_descuento_expirado(self, api_client, prod_dec14):
        ProductDiscount.objects.create(
            product=prod_dec14,
            discount_pct=Decimal('10.00'),
            valid_from=timezone.now() - timedelta(days=10),
            valid_until=timezone.now() - timedelta(days=1),
            is_active=True,
        )
        item = self._get_item(api_client, prod_dec14)
        assert item['discount'] is None

    def test_discount_null_con_descuento_inactivo(self, api_client, prod_dec14):
        ProductDiscount.objects.create(
            product=prod_dec14,
            discount_pct=Decimal('5.00'),
            valid_from=timezone.now() - timedelta(hours=1),
            valid_until=timezone.now() + timedelta(days=7),
            is_active=False,
        )
        item = self._get_item(api_client, prod_dec14)
        assert item['discount'] is None
