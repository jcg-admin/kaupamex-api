"""
Tests de integracion — Sprint 5
UC-CAT-02: Ver Detalle de Producto
UC-CAT-03: Buscar Productos por Texto
UC-CAT-03-EXT: Buscar con Filtros Avanzados
UC-SRCH-01: Full-Text Search con MySQL FULLTEXT
"""
import pytest
from decimal import Decimal

pytestmark = pytest.mark.integration

CATALOGUE_URL  = '/api/v1/catalogue/'
SEARCH_URL     = '/api/v1/catalogue/search/'


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def cat_collares(db):
    from apps.catalogue.models import Category
    return Category.objects.create(name='Collares', slug='collares', is_active=True)


@pytest.fixture
def cat_pulseras(db):
    from apps.catalogue.models import Category
    return Category.objects.create(name='Pulseras', slug='pulseras', is_active=True)


@pytest.fixture
def product_oshun(db, cat_collares):
    from apps.catalogue.models import Product
    return Product.objects.create(
        name='Collar Oshun dorado',
        slug='collar-oshun-dorado',
        sku='OSHUN-001',
        description='Collar sagrado de Oshun para atraer el amor y la prosperidad.',
        short_description='Collar de Oshun dorado.',
        category=cat_collares,
        price=Decimal('1250.00'),
        stock=10,
        is_active=True,
        is_published=True,
    )


@pytest.fixture
def product_yemaya(db, cat_pulseras):
    from apps.catalogue.models import Product
    return Product.objects.create(
        name='Pulsera Yemaya azul',
        slug='pulsera-yemaya-azul',
        sku='YEMAYA-001',
        description='Pulsera de Yemaya para la proteccion del hogar.',
        short_description='Pulsera de Yemaya.',
        category=cat_pulseras,
        price=Decimal('450.00'),
        stock=5,
        is_active=True,
        is_published=True,
    )


@pytest.fixture
def product_sin_stock(db, cat_collares):
    from apps.catalogue.models import Product
    return Product.objects.create(
        name='Collar Shango rojo',
        slug='collar-shango-rojo',
        sku='SHANGO-001',
        description='Collar de Shango.',
        short_description='Collar de Shango.',
        category=cat_collares,
        price=Decimal('980.00'),
        stock=0,
        is_active=True,
        is_published=True,
    )


@pytest.fixture
def product_inactivo(db, cat_collares):
    from apps.catalogue.models import Product
    return Product.objects.create(
        name='Collar inactivo',
        slug='collar-inactivo',
        sku='INACTIVO-001',
        description='Producto inactivo.',
        short_description='.',
        category=cat_collares,
        price=Decimal('100.00'),
        stock=5,
        is_active=False,
        is_published=True,
    )


# =============================================================================
# UC-CAT-02: Ver Detalle de Producto
# =============================================================================

class TestProductoDetalle:

    def test_detalle_retorna_200_por_slug(self, api_client, product_oshun):
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        assert r.status_code == 200

    def test_detalle_contiene_campos_requeridos(self, api_client, product_oshun):
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        data = r.json()
        for campo in ['id', 'name', 'slug', 'sku', 'description',
                      'short_description', 'price', 'price_with_tax',
                      'stock', 'is_active', 'is_published',
                      'category', 'availability']:
            assert campo in data, f'Falta campo: {campo}'

    def test_detalle_retorna_categoria_como_objeto(self, api_client, product_oshun):
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        data = r.json()
        assert isinstance(data['category'], dict)
        assert 'id' in data['category']
        assert 'name' in data['category']
        assert 'slug' in data['category']

    def test_detalle_availability_con_stock(self, api_client, product_oshun):
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        assert r.json()['availability'] == 'available'

    def test_detalle_availability_sin_stock(self, api_client, product_sin_stock):
        r = api_client.get(f'{CATALOGUE_URL}{product_sin_stock.slug}/')
        assert r.json()['availability'] == 'out_of_stock'

    def test_detalle_producto_inexistente_retorna_404(self, api_client):
        r = api_client.get(f'{CATALOGUE_URL}producto-que-no-existe/')
        assert r.status_code == 404

    def test_detalle_producto_inactivo_retorna_404(self, api_client, product_inactivo):
        r = api_client.get(f'{CATALOGUE_URL}{product_inactivo.slug}/')
        assert r.status_code == 404

    def test_detalle_es_publico_sin_autenticar(self, api_client, product_oshun):
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        assert r.status_code == 200

    def test_detalle_incluye_precio_con_iva(self, api_client, product_oshun):
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        data = r.json()
        assert float(data['price_with_tax']) > float(data['price'])


# =============================================================================
# UC-CAT-03 + UC-SRCH-01: Buscar Productos
# =============================================================================

class TestBusqueda:

    def test_busqueda_retorna_200(self, api_client, product_oshun):
        r = api_client.get(SEARCH_URL, {'q': 'oshun'})
        assert r.status_code == 200

    def test_busqueda_retorna_resultados_paginados(self, api_client, product_oshun):
        r = api_client.get(SEARCH_URL, {'q': 'oshun'})
        data = r.json()
        assert 'count' in data
        assert 'results' in data

    def test_busqueda_encuentra_por_nombre(self, api_client, product_oshun, product_yemaya):
        r = api_client.get(SEARCH_URL, {'q': 'oshun'})
        nombres = [p['name'] for p in r.json()['results']]
        assert any('Oshun' in n for n in nombres)
        assert not any('Yemaya' in n for n in nombres)

    def test_busqueda_encuentra_por_descripcion(self, api_client, product_yemaya):
        r = api_client.get(SEARCH_URL, {'q': 'proteccion'})
        assert r.json()['count'] >= 1

    def test_busqueda_no_retorna_inactivos(self, api_client, product_inactivo):
        r = api_client.get(SEARCH_URL, {'q': 'inactivo'})
        assert r.json()['count'] == 0

    def test_busqueda_termino_muy_corto_retorna_400(self, api_client):
        r = api_client.get(SEARCH_URL, {'q': 'a'})
        assert r.status_code == 400

    def test_busqueda_sin_termino_retorna_400(self, api_client):
        r = api_client.get(SEARCH_URL, {})
        assert r.status_code == 400

    def test_busqueda_termino_vacio_retorna_400(self, api_client):
        r = api_client.get(SEARCH_URL, {'q': '   '})
        assert r.status_code == 400

    def test_busqueda_sin_resultados_retorna_lista_vacia(self, api_client, product_oshun):
        r = api_client.get(SEARCH_URL, {'q': 'xyzterm123inexistente'})
        data = r.json()
        assert data['count'] == 0
        assert data['results'] == []

    def test_busqueda_es_publica_sin_autenticar(self, api_client, product_oshun):
        r = api_client.get(SEARCH_URL, {'q': 'oshun'})
        assert r.status_code == 200

    def test_busqueda_retorna_precio_con_iva(self, api_client, product_oshun):
        r = api_client.get(SEARCH_URL, {'q': 'oshun'})
        resultado = r.json()['results'][0]
        assert 'price_with_tax' in resultado

    def test_busqueda_retorna_metadatos_paginacion(self, api_client, product_oshun):
        r = api_client.get(SEARCH_URL, {'q': 'collar'})
        data = r.json()
        assert 'count' in data
        assert 'next' in data
        assert 'previous' in data


# =============================================================================
# UC-CAT-03-EXT: Filtros Avanzados sobre resultados de búsqueda
# =============================================================================

class TestBusquedaFiltrosAvanzados:

    def test_filtro_por_categoria(
        self, api_client, product_oshun, product_yemaya, cat_collares
    ):
        r = api_client.get(SEARCH_URL, {'q': 'collar', 'category': cat_collares.id})
        nombres = [p['name'] for p in r.json()['results']]
        assert any('Oshun' in n for n in nombres)
        assert not any('Yemaya' in n for n in nombres)

    def test_filtro_precio_minimo(self, api_client, product_oshun, product_yemaya):
        # Oshun=1250, Yemaya=450 — precio_min=900 debe excluir Yemaya
        r = api_client.get(SEARCH_URL, {'q': 'collar pulsera', 'price_min': '900'})
        nombres = [p['name'] for p in r.json()['results']]
        assert not any('Yemaya' in n for n in nombres)

    def test_filtro_precio_maximo(self, api_client, product_oshun, product_yemaya):
        # precio_max=600 debe excluir Oshun
        r = api_client.get(SEARCH_URL, {'q': 'collar pulsera', 'price_max': '600'})
        nombres = [p['name'] for p in r.json()['results']]
        assert not any('Oshun' in n for n in nombres)

    def test_filtro_solo_disponibles(
        self, api_client, product_oshun, product_sin_stock
    ):
        r = api_client.get(SEARCH_URL, {'q': 'collar', 'in_stock': 'true'})
        for p in r.json()['results']:
            assert p['stock'] > 0

    def test_filtros_no_requeridos(self, api_client, product_oshun):
        # Sin filtros opcionales debe funcionar igual que búsqueda simple
        r = api_client.get(SEARCH_URL, {'q': 'oshun'})
        assert r.status_code == 200
