"""
Tests — CatalogueListView filters_applied (DEC-BC-16)

T-503: CatalogueListView.list injects filters_applied into paginated response.
T-504: Tests covering GET with filters -> response includes reflection.
"""
import pytest
from decimal import Decimal
from apps.modules.catalogue.models import Category, Product

pytestmark = pytest.mark.integration

CATALOGUE_URL = '/api/v2/products/'


@pytest.fixture
def cat(db):
    return Category.objects.create(name='Ache', slug='ache', is_active=True)


@pytest.fixture
def products(db, cat):
    _p1 = Product.objects.create(
        name='Prod A', slug='prod-a', sku='PA-001',
        description='d', short_description='d',
        price=Decimal('50.00'), stock=5,
        is_active=True, is_published=True,
    )
    _p1.categories.add(cat)
    _p2 = Product.objects.create(
        name='Prod B', slug='prod-b', sku='PB-002',
        description='d', short_description='d',
        price=Decimal('200.00'), stock=0,
        is_active=True, is_published=True,
    )
    _p2.categories.add(cat)


class TestCatalogueActiveFilters:

    def test_no_filters_returns_empty_filters_applied(self, api_client, products):
        r = api_client.get(CATALOGUE_URL)
        assert r.status_code == 200
        assert r.json()['filters_applied'] == {}

    def test_category_filter_reflected(self, api_client, products, cat):
        r = api_client.get(CATALOGUE_URL, {'category': 'ache'})
        assert r.status_code == 200
        data = r.json()
        # T-11/DEC-STF-11: category siempre se refleja como lista (multi).
        assert data['filters_applied']['category'] == ['ache']

    def test_price_min_filter_reflected(self, api_client, products):
        r = api_client.get(CATALOGUE_URL, {'price_min': '100'})
        assert r.status_code == 200
        data = r.json()
        assert data['filters_applied']['price_min'] == '100'

    def test_price_max_filter_reflected(self, api_client, products):
        r = api_client.get(CATALOGUE_URL, {'price_max': '150'})
        assert r.status_code == 200
        data = r.json()
        assert data['filters_applied']['price_max'] == '150'

    def test_multiple_filters_all_reflected(self, api_client, products, cat):
        r = api_client.get(CATALOGUE_URL, {
            'category': 'ache',
            'price_min': '10',
            'price_max': '300',
        })
        assert r.status_code == 200
        fa = r.json()['filters_applied']
        assert fa['category'] == ['ache']
        assert fa['price_min'] == '10'
        assert fa['price_max'] == '300'

    def test_ordering_param_not_in_filters_applied(self, api_client, products):
        r = api_client.get(CATALOGUE_URL, {'ordering': 'novedad'})
        assert r.status_code == 200
        fa = r.json()['filters_applied']
        assert 'ordering' not in fa

    def test_filters_applied_key_always_present(self, api_client, db):
        r = api_client.get(CATALOGUE_URL)
        assert r.status_code == 200
        assert 'filters_applied' in r.json()
