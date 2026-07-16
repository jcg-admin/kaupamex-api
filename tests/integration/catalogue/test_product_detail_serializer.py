"""
Tests — ProductListSerializer and ProductDetailSerializer sub-items

T-403: ProductListSerializer full shape (DEC-BC-14)
T-408: ProductDetailSerializer sub-items 17a (discount) + 17b (images)
       17c (reviews_summary + questions_count) covered in test_product_detail_and_search.py
       17d (price_breakdown) BLOCKED — aval contable required
"""
import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from apps.modules.catalogue.models import Category, Product, ProductDiscount, ProductImage

pytestmark = pytest.mark.integration

CATALOGUE_URL = '/api/v2/products/'


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def cat(db):
    return Category.objects.create(name='Elekes', slug='elekes', is_active=True)


@pytest.fixture
def product(db, cat):
    _p = Product.objects.create(
        name='Elekes Shango',
        slug='elekes-shango',
        sku='SHANGO-ELK',
        description='Elekes tradicionales de Shango.',
        short_description='Elekes Shango.',
        price=Decimal('950.00'),
        stock=8,
        is_active=True,
        is_published=True,
        is_featured=True,
    )
    _p.categories.add(cat)
    return _p


@pytest.fixture
def active_discount(db, product):
    now = timezone.now()
    return ProductDiscount.objects.create(
        product=product,
        discount_pct=Decimal('15.00'),
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=30),
        is_active=True,
    )


@pytest.fixture
def expired_discount(db, product):
    now = timezone.now()
    return ProductDiscount.objects.create(
        product=product,
        discount_pct=Decimal('20.00'),
        valid_from=now - timedelta(days=10),
        valid_until=now - timedelta(days=1),
        is_active=True,
    )


@pytest.fixture
def product_image(db, product):
    return ProductImage.objects.create(
        product=product,
        image='products/images/shango.jpg',
        alt_text='Elekes Shango',
        order=0,
        is_cover=True,
    )


# =============================================================================
# T-403: ProductListSerializer full shape (DEC-BC-14)
# =============================================================================

class TestProductListSerializerShape:

    def test_listado_contiene_main_image(self, api_client, product):
        r = api_client.get(CATALOGUE_URL)
        assert r.status_code == 200
        item = r.json()['results'][0]
        assert 'main_image' in item

    def test_listado_main_image_es_null_sin_imagenes(self, api_client, product):
        r = api_client.get(CATALOGUE_URL)
        item = r.json()['results'][0]
        assert item['main_image'] is None

    def test_listado_main_image_retorna_url_con_imagen(self, api_client, product, product_image):
        r = api_client.get(CATALOGUE_URL)
        item = r.json()['results'][0]
        assert item['main_image'] is not None
        assert 'shango' in item['main_image']

    def test_listado_contiene_discount(self, api_client, product):
        r = api_client.get(CATALOGUE_URL)
        item = r.json()['results'][0]
        assert 'discount' in item

    def test_listado_discount_es_null_sin_descuento(self, api_client, product):
        r = api_client.get(CATALOGUE_URL)
        item = r.json()['results'][0]
        assert item['discount'] is None

    def test_listado_discount_con_descuento_activo(self, api_client, product, active_discount):
        r = api_client.get(CATALOGUE_URL)
        item = r.json()['results'][0]
        d = item['discount']
        assert d is not None
        assert Decimal(str(d['pct'])) == Decimal('15.00')
        assert Decimal(str(d['discounted_price'])) < product.price

    def test_listado_discount_excluye_expirado(self, api_client, product, expired_discount):
        r = api_client.get(CATALOGUE_URL)
        item = r.json()['results'][0]
        assert item['discount'] is None

    def test_listado_contiene_variants_available(self, api_client, product):
        r = api_client.get(CATALOGUE_URL)
        item = r.json()['results'][0]
        assert 'variants_available' in item
        assert isinstance(item['variants_available'], bool)

    def test_listado_variants_available_false_sin_variantes(self, api_client, product):
        r = api_client.get(CATALOGUE_URL)
        item = r.json()['results'][0]
        assert item['variants_available'] is False

    def test_listado_contiene_is_featured(self, api_client, product):
        r = api_client.get(CATALOGUE_URL)
        item = r.json()['results'][0]
        assert 'is_featured' in item
        assert item['is_featured'] is True


# =============================================================================
# T-408: ProductDetailSerializer — sub-items 17a (discount) + 17b (images)
# =============================================================================

class TestProductDetailDiscount:

    def test_detalle_discount_es_null_sin_descuento(self, api_client, product):
        r = api_client.get(f'{CATALOGUE_URL}{product.slug}/')
        assert r.json()['discount'] is None

    def test_detalle_discount_retorna_estructura_correcta(self, api_client, product, active_discount):
        r = api_client.get(f'{CATALOGUE_URL}{product.slug}/')
        d = r.json()['discount']
        assert d is not None
        assert 'pct' in d
        assert 'original_price' in d
        assert 'discounted_price' in d

    def test_detalle_discount_pct_correcto(self, api_client, product, active_discount):
        r = api_client.get(f'{CATALOGUE_URL}{product.slug}/')
        assert Decimal(str(r.json()['discount']['pct'])) == Decimal('15.00')

    def test_detalle_discount_discounted_price_correcto(self, api_client, product, active_discount):
        r = api_client.get(f'{CATALOGUE_URL}{product.slug}/')
        d = r.json()['discount']
        expected = (product.price * Decimal('0.85')).quantize(Decimal('0.01'))
        assert abs(Decimal(str(d['discounted_price'])) - expected) < Decimal('0.01')

    def test_detalle_discount_excluye_expirado(self, api_client, product, expired_discount):
        r = api_client.get(f'{CATALOGUE_URL}{product.slug}/')
        assert r.json()['discount'] is None


class TestProductDetailImages:

    def test_detalle_images_es_lista_vacia_sin_imagenes(self, api_client, product):
        r = api_client.get(f'{CATALOGUE_URL}{product.slug}/')
        assert r.json()['images'] == []

    def test_detalle_images_retorna_lista(self, api_client, product, product_image):
        r = api_client.get(f'{CATALOGUE_URL}{product.slug}/')
        imgs = r.json()['images']
        assert isinstance(imgs, list)
        assert len(imgs) == 1

    def test_detalle_images_contiene_campos_correctos(self, api_client, product, product_image):
        r = api_client.get(f'{CATALOGUE_URL}{product.slug}/')
        img = r.json()['images'][0]
        assert 'id' in img
        assert 'image' in img
        assert 'alt_text' in img
        assert 'order' in img
