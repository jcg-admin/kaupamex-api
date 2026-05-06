"""
Tests de integracion — Catalogo de productos
UC-CAT-01: Ver Catalogo de Productos
"""
import pytest
from decimal import Decimal

pytestmark = pytest.mark.integration

CATALOGUE_URL = '/api/v1/catalogue/'


@pytest.fixture
def category(db):
    from apps.catalogue.models import Category
    return Category.objects.create(name='Collares', slug='collares', is_active=True)


@pytest.fixture
def products(db, category):
    from apps.catalogue.models import Product
    prods = []
    for i in range(5):
        prods.append(Product.objects.create(
            name=f'Collar Oshun {i}',
            slug=f'collar-oshun-{i}',
            sku=f'COLLAR-{i:03}',
            description='Collar sagrado',
            category=category,
            price=Decimal('1250.00'),
            is_active=True,
            is_published=True,
        ))
    return prods


class TestCatalogueList:

    def test_catalogo_retorna_200_sin_autenticar(self, api_client, db):
        r = api_client.get(CATALOGUE_URL)
        assert r.status_code == 200

    def test_catalogo_retorna_lista_paginada(self, api_client, products, db):
        r = api_client.get(CATALOGUE_URL)
        data = r.json()
        assert 'count' in data
        assert 'results' in data

    def test_catalogo_solo_muestra_activos_y_publicados(self, api_client, products, category, db):
        from apps.catalogue.models import Product
        Product.objects.create(
            name='Inactivo', slug='inactivo', sku='INACT-001',
            description='', category=category,
            price=Decimal('100.00'), is_active=False, is_published=True,
        )
        r = api_client.get(CATALOGUE_URL)
        slugs = [p['slug'] for p in r.json()['results']]
        assert 'inactivo' not in slugs

    def test_respuesta_incluye_price_with_tax(self, api_client, products, db):
        r = api_client.get(CATALOGUE_URL)
        product = r.json()['results'][0]
        assert 'price_with_tax' in product

    def test_filtro_por_categoria(self, api_client, products, category, db):
        r = api_client.get(CATALOGUE_URL, {'category': 'collares'})
        assert r.status_code == 200
        assert r.json()['count'] == 5

    def test_filtro_categoria_inexistente_retorna_lista_vacia(self, api_client, db):
        r = api_client.get(CATALOGUE_URL, {'category': 'no-existe'})
        assert r.json()['count'] == 0

    def test_ordenamiento_por_precio_ascendente(self, api_client, category, db):
        from apps.catalogue.models import Product
        Product.objects.create(name='Barato', slug='barato', sku='BAR-001',
                               description='', category=category,
                               price=Decimal('100.00'), is_active=True, is_published=True)
        Product.objects.create(name='Caro', slug='caro', sku='CAR-001',
                               description='', category=category,
                               price=Decimal('9000.00'), is_active=True, is_published=True)
        r = api_client.get(CATALOGUE_URL, {'ordering': 'price'})
        prices = [p['base_price'] for p in r.json()['results']]
        assert prices == sorted(prices)

    def test_producto_inactivo_no_aparece(self, api_client, category, db):
        from apps.catalogue.models import Product
        p = Product.objects.create(
            name='Borrador', slug='borrador', sku='BOR-001',
            description='', category=category,
            price=Decimal('500.00'), is_active=False, is_published=True,
        )
        r = api_client.get(CATALOGUE_URL)
        slugs = [item['slug'] for item in r.json()['results']]
        assert 'borrador' not in slugs
