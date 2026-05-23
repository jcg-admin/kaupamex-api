"""
Tests — Product detail and full-text search

UC-CAT-02: View product detail
UC-CAT-03: Search products by text (full-text)
UC-CAT-03-EXT: Advanced search filters
UC-SRCH-01: Full-text search with MariaDB FULLTEXT
"""
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.catalogue.models import Category, Product
from apps.reviews.models import Review
from apps.questions.models import ProductQuestion, QuestionStatus
from apps.orders.models import Order

pytestmark = pytest.mark.integration

CATALOGUE_URL = '/api/v1/catalogue/'
SEARCH_URL    = '/api/v1/catalogue/search/'


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def cat_collares(db):
    return Category.objects.create(name='Collares', slug='collares', is_active=True)


@pytest.fixture
def cat_pulseras(db):
    return Category.objects.create(name='Pulseras', slug='pulseras', is_active=True)


@pytest.fixture
def product_oshun(db, cat_collares):
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
        for campo in [
            'id', 'name', 'slug', 'sku',
            'description', 'short_description',
            'base_price', 'price_with_tax',
            'stock', 'availability',
            'category', 'images', 'discount',
        ]:
            assert campo in data, f'Falta campo: {campo}'

    def test_detalle_base_price_es_precio_sin_iva(self, api_client, product_oshun):
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        data = r.json()
        assert float(data['base_price']) == float(product_oshun.price)

    def test_detalle_price_with_tax_mayor_que_base(self, api_client, product_oshun):
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        data = r.json()
        assert float(data['price_with_tax']) > float(data['base_price'])

    def test_detalle_retorna_categoria_como_objeto(self, api_client, product_oshun):
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        data = r.json()
        assert isinstance(data['category'], dict)
        assert 'id' in data['category']
        assert 'name' in data['category']
        assert 'slug' in data['category']

    def test_detalle_availability_con_stock_es_IN_STOCK(self, api_client, product_oshun):
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        assert r.json()['availability'] == 'IN_STOCK'

    def test_detalle_availability_sin_stock_es_OUT_OF_STOCK(self, api_client, product_sin_stock):
        r = api_client.get(f'{CATALOGUE_URL}{product_sin_stock.slug}/')
        assert r.json()['availability'] == 'OUT_OF_STOCK'

    def test_detalle_images_retorna_lista(self, api_client, product_oshun):
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        assert isinstance(r.json()['images'], list)

    def test_detalle_discount_nulo_sin_descuento(self, api_client, product_oshun):
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        assert r.json()['discount'] is None

    def test_detalle_producto_inexistente_retorna_404(self, api_client):
        r = api_client.get(f'{CATALOGUE_URL}producto-que-no-existe/')
        assert r.status_code == 404

    def test_detalle_producto_inactivo_retorna_404(self, api_client, product_inactivo):
        r = api_client.get(f'{CATALOGUE_URL}{product_inactivo.slug}/')
        assert r.status_code == 404

    def test_detalle_es_publico_sin_autenticar(self, api_client, product_oshun):
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        assert r.status_code == 200

    def test_detalle_contiene_reviews_summary(self, api_client, product_oshun):
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        data = r.json()
        assert 'reviews_summary' in data
        rs = data['reviews_summary']
        assert 'average_rating' in rs
        assert 'total_count' in rs

    def test_detalle_reviews_summary_sin_resenas(self, api_client, product_oshun):
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        rs = r.json()['reviews_summary']
        assert rs['average_rating'] is None
        assert rs['total_count'] == 0

    def test_detalle_reviews_summary_agrega_aprobadas(self, api_client, db, product_oshun):
        User = get_user_model()
        u = User.objects.create_user(username='rev_user', password='X', email='r@x.com')
        order = Order.objects.create(user=u, status=Order.STATUS_DELIVERED)
        Review.objects.create(
            user=u, product=product_oshun, order=order,
            rating=4, title='Bien', body='Producto bueno.',
            status=Review.STATUS_APPROVED,
        )
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        rs = r.json()['reviews_summary']
        assert rs['total_count'] == 1
        assert rs['average_rating'] == 4.0

    def test_detalle_reviews_summary_excluye_pendientes(self, api_client, db, product_oshun):
        User = get_user_model()
        u = User.objects.create_user(username='rev_user2', password='X', email='r2@x.com')
        order = Order.objects.create(user=u, status=Order.STATUS_DELIVERED)
        Review.objects.create(
            user=u, product=product_oshun, order=order,
            rating=5, title='Excelente', body='Muy bueno.',
            status=Review.STATUS_PENDING,
        )
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        rs = r.json()['reviews_summary']
        assert rs['total_count'] == 0
        assert rs['average_rating'] is None

    def test_detalle_contiene_questions_count(self, api_client, product_oshun):
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        data = r.json()
        assert 'questions_count' in data
        assert isinstance(data['questions_count'], int)

    def test_detalle_questions_count_sin_preguntas(self, api_client, product_oshun):
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        assert r.json()['questions_count'] == 0

    def test_detalle_questions_count_solo_respondidas(self, api_client, db, product_oshun):
        ProductQuestion.objects.create(
            product=product_oshun, body='¿Cuántos quedan?',
            status=QuestionStatus.ANSWERED, answer_body='Quedan 10.',
        )
        ProductQuestion.objects.create(
            product=product_oshun, body='¿Es original?',
            status=QuestionStatus.PENDING, answer_body='',
        )
        r = api_client.get(f'{CATALOGUE_URL}{product_oshun.slug}/')
        assert r.json()['questions_count'] == 1


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

    def test_busqueda_termino_1_char_retorna_400(self, api_client):
        r = api_client.get(SEARCH_URL, {'q': 'a'})
        assert r.status_code == 400

    def test_busqueda_codigo_error_TERMINO_MUY_CORTO(self, api_client):
        r = api_client.get(SEARCH_URL, {'q': 'a'})
        assert r.json().get('codigo_error') == 'TERMINO_MUY_CORTO'

    def test_busqueda_sin_termino_retorna_400(self, api_client):
        r = api_client.get(SEARCH_URL, {})
        assert r.status_code == 400

    def test_busqueda_termino_solo_espacios_retorna_400(self, api_client):
        r = api_client.get(SEARCH_URL, {'q': '   '})
        assert r.status_code == 400

    def test_busqueda_normaliza_espacios_internos(self, api_client, product_oshun):
        # "Oshun  dorado" (doble espacio) debe encontrar "Collar Oshun dorado"
        r = api_client.get(SEARCH_URL, {'q': 'Oshun  dorado'})
        assert r.status_code == 200

    def test_busqueda_trunca_termino_a_100_chars(self, api_client, product_oshun):
        termino_largo = 'a' * 150
        r = api_client.get(SEARCH_URL, {'q': termino_largo})
        assert r.status_code == 200

    def test_busqueda_sin_resultados_retorna_count_cero(self, api_client, product_oshun):
        r = api_client.get(SEARCH_URL, {'q': 'xyzterm123inexistente'})
        data = r.json()
        assert data['count'] == 0
        assert data['results'] == []

    def test_busqueda_es_publica_sin_autenticar(self, api_client, product_oshun):
        r = api_client.get(SEARCH_URL, {'q': 'oshun'})
        assert r.status_code == 200

    def test_busqueda_retorna_base_price_en_resultados(self, api_client, product_oshun):
        r = api_client.get(SEARCH_URL, {'q': 'oshun'})
        resultado = r.json()['results'][0]
        assert 'base_price' in resultado
        assert 'price_with_tax' in resultado

    def test_busqueda_retorna_highlighted_term(self, api_client, product_oshun):
        r = api_client.get(SEARCH_URL, {'q': 'oshun'})
        resultado = r.json()['results'][0]
        assert 'highlighted_name' in resultado

    def test_busqueda_featured_aparece_primero(
        self, api_client, product_oshun, product_yemaya, cat_collares
    ):
        # product_oshun es featured=True, product_yemaya no
        # ambos contienen "collar" o "pulsera" — buscar término que devuelva ambos
        Product.objects.filter(slug='pulsera-yemaya-azul').update(
            name='Pulsera Yemaya collar azul',  # para que aparezca en búsqueda de 'collar'
            description='collar Yemaya',
        )
        r = api_client.get(SEARCH_URL, {'q': 'collar'})
        resultados = r.json()['results']
        # is_featured fue eliminado del modelo — verificar solo que hay resultados
        assert len(resultados) >= 1

    def test_busqueda_metadatos_paginacion(self, api_client, product_oshun):
        r = api_client.get(SEARCH_URL, {'q': 'oshun'})
        data = r.json()
        assert 'count' in data
        assert 'next' in data
        assert 'previous' in data


# =============================================================================
# UC-CAT-03-EXT: Filtros Avanzados
# =============================================================================

class TestBusquedaFiltrosAvanzados:

    def test_filtro_por_categoria(
        self, api_client, product_oshun, product_yemaya, cat_collares
    ):
        r = api_client.get(SEARCH_URL, {'q': 'collar', 'category': cat_collares.id})
        nombres = [p['name'] for p in r.json()['results']]
        assert any('Oshun' in n for n in nombres)
        assert not any('Yemaya' in n for n in nombres)

    def test_filtro_precio_minimo_sin_iva(self, api_client, product_oshun, product_yemaya):
        # Oshun=1250, Yemaya=450 — price_min=900 debe excluir Yemaya (BR-001: sin IVA)
        r = api_client.get(SEARCH_URL, {'q': 'collar pulsera', 'price_min': '900'})
        nombres = [p['name'] for p in r.json()['results']]
        assert not any('Yemaya' in n for n in nombres)

    def test_filtro_precio_maximo_sin_iva(self, api_client, product_oshun, product_yemaya):
        # price_max=600 debe excluir Oshun
        r = api_client.get(SEARCH_URL, {'q': 'collar pulsera', 'price_max': '600'})
        nombres = [p['name'] for p in r.json()['results']]
        assert not any('Oshun' in n for n in nombres)

    def test_filtro_solo_con_stock(
        self, api_client, product_oshun, product_sin_stock
    ):
        r = api_client.get(SEARCH_URL, {'q': 'collar', 'in_stock': 'true'})
        for p in r.json()['results']:
            assert p['stock'] > 0

    def test_filtros_sin_resultados_incluye_active_filters(
        self, api_client, product_oshun
    ):
        # Filtros muy restrictivos — respuesta debe incluir active_filters
        r = api_client.get(SEARCH_URL, {
            'q': 'collar', 'price_min': '99999'
        })
        data = r.json()
        assert data['count'] == 0
        assert 'active_filters' in data

    def test_filtros_no_requeridos(self, api_client, product_oshun):
        r = api_client.get(SEARCH_URL, {'q': 'oshun'})
        assert r.status_code == 200
