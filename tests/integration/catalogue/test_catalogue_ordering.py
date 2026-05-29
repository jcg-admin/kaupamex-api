"""
Tests — CatalogueOrderingFilter (DEC-BC-15)

T-501: CatalogueOrderingFilter maps ES kebab aliases to DRF ordering.
T-502: Tests covering valid alias -> correct order, invalid -> 400.
"""
import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from apps.catalogue.models import Category, Product

pytestmark = pytest.mark.integration

CATALOGUE_URL = '/api/v1/catalogue/'


@pytest.fixture
def cat(db):
    return Category.objects.create(name='Orisha', slug='orisha', is_active=True)


@pytest.fixture
def products(db, cat):
    now = timezone.now()
    p1 = Product.objects.create(
        name='Ache', slug='ache', sku='ACHE-001',
        description='d', short_description='d',
        price=Decimal('100.00'), stock=5,
        is_active=True, is_published=True,
    )
    p1.categories.add(cat)
    p1.categories.add(cat)
    p2 = Product.objects.create(
        name='Bata', slug='bata', sku='BATA-002',
        description='d', short_description='d',
        price=Decimal('300.00'), stock=3,
        is_active=True, is_published=True,
    )
    p2.categories.add(cat)
    p2.categories.add(cat)
    p3 = Product.objects.create(
        name='Clave', slug='clave', sku='CLAV-003',
        description='d', short_description='d',
        price=Decimal('200.00'), stock=2,
        is_active=True, is_published=True,
    )
    p3.categories.add(cat)
    p3.categories.add(cat)
    # auto_now_add bypassed via update() for deterministic date ordering
    Product.objects.filter(pk=p1.pk).update(created_at=now - timedelta(days=2))
    Product.objects.filter(pk=p2.pk).update(created_at=now - timedelta(days=1))
    Product.objects.filter(pk=p3.pk).update(created_at=now)
    return [p1, p2, p3]


class TestCatalogueOrdering:

    def test_default_ordering_mas_reciente_primero(self, api_client, products):
        r = api_client.get(CATALOGUE_URL)
        assert r.status_code == 200
        names = [item['name'] for item in r.json()['results']]
        assert names == ['Clave', 'Bata', 'Ache']

    def test_novedad_ordering(self, api_client, products):
        r = api_client.get(CATALOGUE_URL, {'ordering': 'novedad'})
        assert r.status_code == 200
        names = [item['name'] for item in r.json()['results']]
        assert names == ['Clave', 'Bata', 'Ache']

    def test_precio_asc_ordering(self, api_client, products):
        r = api_client.get(CATALOGUE_URL, {'ordering': 'precio-asc'})
        assert r.status_code == 200
        prices = [float(item['base_price']) for item in r.json()['results']]
        assert prices == sorted(prices)

    def test_precio_desc_ordering(self, api_client, products):
        r = api_client.get(CATALOGUE_URL, {'ordering': 'precio-desc'})
        assert r.status_code == 200
        prices = [float(item['base_price']) for item in r.json()['results']]
        assert prices == sorted(prices, reverse=True)

    def test_nombre_asc_ordering(self, api_client, products):
        r = api_client.get(CATALOGUE_URL, {'ordering': 'nombre'})
        assert r.status_code == 200
        names = [item['name'] for item in r.json()['results']]
        assert names == sorted(names)

    def test_nombre_desc_ordering(self, api_client, products):
        r = api_client.get(CATALOGUE_URL, {'ordering': 'nombre-desc'})
        assert r.status_code == 200
        names = [item['name'] for item in r.json()['results']]
        assert names == sorted(names, reverse=True)

    def test_ordering_invalido_retorna_400(self, api_client, products):
        r = api_client.get(CATALOGUE_URL, {'ordering': 'inexistente'})
        assert r.status_code == 400

    def test_ordering_invalido_codigo_error(self, api_client, products):
        r = api_client.get(CATALOGUE_URL, {'ordering': 'inexistente'})
        assert r.json()['codigo_error'] == 'INVALID_ORDERING'

    def test_ordering_invalido_lista_valores_validos(self, api_client, products):
        r = api_client.get(CATALOGUE_URL, {'ordering': 'bad'})
        data = r.json()
        assert 'valores_validos' in data
        assert 'precio-asc' in data['valores_validos']
        assert 'novedad' in data['valores_validos']
