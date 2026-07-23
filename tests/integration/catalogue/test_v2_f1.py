"""
Tests de integracion — API v2 F1: superficie unificada de productos

Verifica que los endpoints /api/v2/ son funcionales y devuelven las
respuestas correctas para los tres modos del endpoint unificado:
  - lista (sin ?q=)
  - busqueda (?q=<term>)
  - autocomplete (?q=<term>&autocomplete=1)

F1 no migra datos ni elimina v1; verifica coexistencia.
"""
import pytest
from decimal import Decimal
from addons.catalogue.models import Category, Product

pytestmark = pytest.mark.integration

V2_PRODUCTS_URL = '/api/v2/products/'
V2_CATEGORIES_URL = '/api/v2/categories/'


@pytest.fixture
def category(db):
    return Category.objects.create(name='Elekes', slug='elekes', is_active=True)


@pytest.fixture
def products(db, category):
    prods = []
    for i in range(3):
        p = Product.objects.create(
            name=f'Eleke Oshun {i}',
            slug=f'eleke-oshun-{i}',
            sku=f'ELEK-{i:03}',
            description='Eleke sagrado de Oshun',
            price=Decimal('850.00'),
            is_active=True,
            is_published=True,
        )
        p.categories.add(category)
        prods.append(p)
    return prods


class TestProductListV2:

    def test_list_returns_200_unauthenticated(self, api_client, db):
        r = api_client.get(V2_PRODUCTS_URL)
        assert r.status_code == 200

    def test_list_returns_paginated_response(self, api_client, products, db):
        r = api_client.get(V2_PRODUCTS_URL)
        data = r.json()
        assert 'count' in data
        assert 'results' in data
        assert isinstance(data['results'], list)

    def test_list_excludes_inactive_products(self, api_client, db, category):
        Product.objects.create(
            name='Inactivo', slug='inactivo', sku='INACT-V2-001',
            description='', price=Decimal('100.00'),
            is_active=False, is_published=True,
        )
        r = api_client.get(V2_PRODUCTS_URL)
        slugs = [p['slug'] for p in r.json()['results']]
        assert 'inactivo' not in slugs

    def test_list_filter_in_stock(self, api_client, db, category):
        Product.objects.create(
            name='Sin stock', slug='sin-stock-v2', sku='NOSTK-V2-001',
            description='', price=Decimal('200.00'),
            is_active=True, is_published=True, stock=0,
        )
        r = api_client.get(V2_PRODUCTS_URL, {'in_stock': 'true'})
        assert r.status_code == 200
        slugs = [p['slug'] for p in r.json()['results']]
        assert 'sin-stock-v2' not in slugs


class TestProductSearchV2:

    def test_search_returns_200(self, api_client, products, db):
        r = api_client.get(V2_PRODUCTS_URL, {'q': 'eleke'})
        assert r.status_code == 200

    def test_search_returns_active_filters_key(self, api_client, products, db):
        r = api_client.get(V2_PRODUCTS_URL, {'q': 'eleke'})
        data = r.json()
        assert 'active_filters' in data

    def test_search_short_query_returns_400(self, api_client, db):
        r = api_client.get(V2_PRODUCTS_URL, {'q': 'x'})
        assert r.status_code == 400

    def test_search_nonexistent_category_returns_empty(self, api_client, products, db):
        # T-11/DEC-STF-11: busqueda filtra por slug (no por ID). Un slug
        # inexistente ya no es 400 ("debe ser entero"); devuelve 200 vacio,
        # igual que el modo lista.
        r = api_client.get(V2_PRODUCTS_URL, {'q': 'eleke', 'category': 'no-existe'})
        assert r.status_code == 200
        assert r.json()['count'] == 0

    def test_search_price_filter_applied(self, api_client, db, category):
        Product.objects.create(
            name='Eleke caro', slug='eleke-caro', sku='ELKCR-001',
            description='', price=Decimal('5000.00'),
            is_active=True, is_published=True,
        )
        r = api_client.get(V2_PRODUCTS_URL, {'q': 'eleke', 'price_max': '1000'})
        assert r.status_code == 200
        slugs = [p['slug'] for p in r.json()['results']]
        assert 'eleke-caro' not in slugs

    def test_search_negative_price_returns_400(self, api_client, products, db):
        r = api_client.get(V2_PRODUCTS_URL, {'q': 'eleke', 'price_min': '-1'})
        assert r.status_code == 400


class TestAutocompleteV2:

    def test_autocomplete_returns_list(self, api_client, products, db):
        r = api_client.get(V2_PRODUCTS_URL, {'q': 'ele', 'autocomplete': '1'})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_autocomplete_short_prefix_returns_empty(self, api_client, products, db):
        r = api_client.get(V2_PRODUCTS_URL, {'q': 'e', 'autocomplete': '1'})
        assert r.status_code == 200
        assert r.json() == []

    def test_autocomplete_returns_id_name_slug(self, api_client, products, db):
        r = api_client.get(V2_PRODUCTS_URL, {'q': 'ele', 'autocomplete': '1'})
        assert r.status_code == 200
        results = r.json()
        if results:
            item = results[0]
            assert 'id' in item
            assert 'name' in item
            assert 'slug' in item


class TestProductDetailV2:

    def test_detail_returns_200(self, api_client, products, db):
        slug = products[0].slug
        r = api_client.get(f'/api/v2/products/{slug}/')
        assert r.status_code == 200

    def test_detail_returns_404_for_unknown_slug(self, api_client, db):
        r = api_client.get('/api/v2/products/no-existe/')
        assert r.status_code == 404


class TestCategoryListV2:

    def test_categories_returns_200(self, api_client, category, db):
        r = api_client.get(V2_CATEGORIES_URL)
        assert r.status_code == 200

    def test_v1_and_v2_categories_coexist(self, api_client, category, db):
        r1 = api_client.get('/api/v2/categories/')
        r2 = api_client.get(V2_CATEGORIES_URL)
        assert r1.status_code == 200
        assert r2.status_code == 200
