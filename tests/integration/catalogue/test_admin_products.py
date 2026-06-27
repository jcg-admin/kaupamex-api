"""
Tests — Admin product and category management

UC-CAT-07: View related products
UC-CAT-08: List categories (hierarchical tree)
UC-CAT-09: Create product (admin)
UC-CAT-10: Edit product (admin)
"""
import pytest
from decimal import Decimal
from apps.catalogue.models import Category, Product, ProductImage
from apps.orders.models import Order, OrderItem
from django.core.cache import cache
from apps.catalogue.serializers import ProductAdminSerializer

pytestmark = pytest.mark.integration

CATALOGUE_URL  = '/api/v2/catalogue/'
CATEGORIES_URL = '/api/v2/catalogue/categories/'
ADMIN_PROD_URL = '/api/v2/admin/products/'


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def cat_soperas(db):
    return Category.objects.create(name='Soperas', slug='soperas', is_active=True)


@pytest.fixture
def cat_soperas_grandes(db, cat_soperas):
    return Category.objects.create(
        name='Soperas Grandes', slug='soperas-grandes',
        parent=cat_soperas, is_active=True,
    )


@pytest.fixture
def cat_pulseras(db):
    return Category.objects.create(name='Pulseras', slug='pulseras', is_active=True)


@pytest.fixture
def product_sopera(db, cat_soperas):
    _p = Product.objects.create(
        name='Sopera Yemaya', slug='sopera-yemaya', sku='SOP-YEM-001',
        description='Sopera sagrada de Yemaya',
        price=Decimal('3200.00'), stock=2,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_soperas)
    return _p


@pytest.fixture
def products_soperas(db, cat_soperas):
    """5 productos en cat_soperas para testear related."""
    prods = []
    for i in range(5):
        _p = Product.objects.create(
            name=f'Sopera Orisha {i}', slug=f'sopera-orisha-{i}', sku=f'SOP-{i:03}',
            description='',
            price=Decimal('2000.00'), stock=1,
            is_active=True, is_published=True,
        )
        _p.categories.add(cat_soperas)
        prods.append(_p)
    return prods


@pytest.fixture
def product_pulsera(db, cat_pulseras):
    _p = Product.objects.create(
        name='Pulsera Elegua', slug='pulsera-elegua-s7', sku='PUL-ELE-001',
        description='Pulsera sagrada de Elegua',
        price=Decimal('480.00'), stock=10,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_pulseras)
    return _p


# =============================================================================
# UC-CAT-07 — Productos relacionados (TST-FR-CAT-07.02)
# =============================================================================

class TestProductosRelacionados:

    def test_ficha_incluye_related_products(
        self, api_client, product_sopera, products_soperas, db
    ):
        """TST-FR-CAT-07.02 Escenario 1: 4 relacionados disponibles."""
        res = api_client.get(f'{CATALOGUE_URL}{product_sopera.slug}/')
        assert res.status_code == 200
        data = res.json()
        assert 'related_products' in data
        related = data['related_products']
        assert len(related) == 4
        # El producto actual no debe estar en los relacionados
        slugs = [p['slug'] for p in related]
        assert product_sopera.slug not in slugs

    def test_relacionados_misma_categoria(
        self, api_client, product_sopera, product_pulsera, products_soperas, db
    ):
        """TST-FR-CAT-07.02 Escenario 2: solo misma categoría."""
        res = api_client.get(f'{CATALOGUE_URL}{product_sopera.slug}/')
        assert res.status_code == 200
        related = res.json()['related_products']
        slugs = [p['slug'] for p in related]
        assert product_pulsera.slug not in slugs

    def test_relacionados_maximos_cuatro(
        self, api_client, product_sopera, products_soperas, db
    ):
        """TST-FR-CAT-07.02: máximo 4 resultados."""
        res = api_client.get(f'{CATALOGUE_URL}{product_sopera.slug}/')
        assert res.status_code == 200
        assert len(res.json()['related_products']) <= 4

    def test_relacionados_solo_activos_publicados(
        self, api_client, product_sopera, cat_soperas, db
    ):
        Product.objects.create(
            name='Inactivo', slug='inactivo-rel', sku='INACT-001',
            description='',
            price=Decimal('100.00'), stock=0,
            is_active=False, is_published=False,
        )
        res = api_client.get(f'{CATALOGUE_URL}{product_sopera.slug}/')
        assert res.status_code == 200
        for p in res.json()['related_products']:
            assert p['slug'] != 'inactivo-rel'


# =============================================================================
# UC-CAT-08 — Árbol de categorías público (TST-FR-CAT-08.01/02)
# =============================================================================

class TestCategoryTree:

    def test_listado_categorias_activas(
        self, api_client, cat_soperas, cat_pulseras, db
    ):
        """TST-FR-CAT-08.01 Escenario 1: retorna solo categorías activas."""
        Category.objects.create(name='Inactiva', slug='inactiva', is_active=False)
        res = api_client.get(CATEGORIES_URL)
        assert res.status_code == 200
        nombres = [c['name'] for c in res.json()]
        assert 'Soperas' in nombres
        assert 'Pulseras' in nombres
        assert 'Inactiva' not in nombres

    def test_estructura_arbol_con_hijos(
        self, api_client, cat_soperas, cat_soperas_grandes, db
    ):
        """TST-FR-CAT-08.01: categorías con subcategorías."""
        res = api_client.get(CATEGORIES_URL)
        assert res.status_code == 200
        soperas_node = next((c for c in res.json() if c['name'] == 'Soperas'), None)
        assert soperas_node is not None
        assert any(c['name'] == 'Soperas Grandes' for c in soperas_node.get('children', []))

    def test_product_count_en_nodo(
        self, api_client, cat_soperas, product_sopera, db
    ):
        """TST-FR-CAT-08.02: product_count incluye productos activos y publicados."""
        cache.delete('categories:tree')
        res = api_client.get(CATEGORIES_URL)
        assert res.status_code == 200
        soperas_node = next((c for c in res.json() if c['name'] == 'Soperas'), None)
        assert soperas_node is not None
        assert soperas_node['product_count'] >= 1

    def test_product_count_acumulado_en_padre(
        self, api_client, cat_soperas, cat_soperas_grandes, db
    ):
        """FR-CAT-08.02: product_count del padre incluye productos de subcategorías."""
        _p = Product.objects.create(
            name='Sopera Grande X', slug='sopera-grande-x', sku='SGX-001',
            description='',
            price=Decimal('5000.00'), stock=1,
            is_active=True, is_published=True,
        )
        _p.categories.add(cat_soperas_grandes)
        cache.delete('categories:tree')
        res = api_client.get(CATEGORIES_URL)
        assert res.status_code == 200
        soperas_node = next((c for c in res.json() if c['name'] == 'Soperas'), None)
        assert soperas_node is not None
        assert soperas_node['product_count'] >= 1

    def test_category_tree_cacheado(
        self, api_client, cat_soperas, db
    ):
        """FR-CAT-08.02: segunda solicitud es cacheada."""
        cache.delete('categories:tree')
        api_client.get(CATEGORIES_URL)
        assert cache.get('categories:tree') is not None


# =============================================================================
# UC-CAT-09 — Crear producto admin (TST-FR-CAT-09.02)
# =============================================================================

class TestCrearProductoAdmin:

    def test_crear_producto_exitoso(self, admin_client, cat_soperas, db):
        """TST-FR-CAT-09.02 Escenario 1: creación completa."""
        res = admin_client.post(ADMIN_PROD_URL, {
            'name':        'Brazalete Yemaya Dorado',
            'sku':         'BRZ-YEM-D01',
            'category_id': cat_soperas.pk,
            'base_price':  '1800.00',
            'stock':       10,
        }, format='json')
        assert res.status_code == 201
        data = res.json()
        assert data['name'] == 'Brazalete Yemaya Dorado'
        assert data['sku']  == 'BRZ-YEM-D01'
        assert 'price_with_tax' in data
        assert data['is_published'] is False

    def test_crear_producto_slug_autogenerado(
        self, admin_client, cat_soperas, db
    ):
        """Slug generado desde name si no se envía."""
        res = admin_client.post(ADMIN_PROD_URL, {
            'name': 'Brazalete Yemaya Dorado',
            'sku':  'BRZ-YEM-D02',
            'category_id': cat_soperas.pk,
            'base_price': '1800.00',
        }, format='json')
        assert res.status_code == 201
        assert res.json()['slug'] == 'brazalete-yemaya-dorado'

    def test_crear_producto_sku_duplicado_retorna_409(
        self, admin_client, cat_soperas, product_sopera, db
    ):
        """TST-FR-CAT-09.02 Escenario 2: SKU duplicado retorna 409 CONFLICT (DuplicateSKUError)."""
        res = admin_client.post(ADMIN_PROD_URL, {
            'name': 'Otro Producto',
            'sku':  product_sopera.sku,  # mismo SKU
            'category_id': cat_soperas.pk,
            'base_price': '100.00',
        }, format='json')
        assert res.status_code == 409

    def test_crear_producto_categoria_inexistente_retorna_400(
        self, admin_client, db
    ):
        res = admin_client.post(ADMIN_PROD_URL, {
            'name': 'Test', 'sku': 'TST-999',
            'category_ids': [99999],
            'base_price': '100.00',
        }, format='json')
        assert res.status_code == 400

    def test_crear_producto_precio_negativo_retorna_400(
        self, admin_client, cat_soperas, db
    ):
        res = admin_client.post(ADMIN_PROD_URL, {
            'name': 'Test neg', 'sku': 'TST-NEG-001',
            'category_id': cat_soperas.pk,
            'base_price': '-10.00',
        }, format='json')
        assert res.status_code == 400

    def test_respuesta_incluye_price_with_tax(self, admin_client, cat_soperas, db):
        res = admin_client.post(ADMIN_PROD_URL, {
            'name': 'Producto con IVA', 'sku': 'IVA-001',
            'category_id': cat_soperas.pk, 'base_price': '1000.00',
        }, format='json')
        assert res.status_code == 201
        assert 'price_with_tax' in res.json()


# =============================================================================
# UC-CAT-10 — Editar producto admin (TST-FR-CAT-10.02)
# =============================================================================

class TestEditarProductoAdmin:

    def test_editar_precio_exitoso(self, admin_client, product_sopera, db):
        """TST-FR-CAT-10.02 Escenario 1: precio editado."""
        res = admin_client.patch(
            f'{ADMIN_PROD_URL}{product_sopera.pk}/',
            {'base_price': '3500.00'},
            format='json',
        )
        assert res.status_code == 200
        assert res.json()['base_price'] == '3500.00'

    def test_editar_solo_campos_enviados(
        self, admin_client, product_sopera, db
    ):
        """PATCH semantics: campos no enviados no se modifican."""
        original_name = product_sopera.name
        res = admin_client.patch(
            f'{ADMIN_PROD_URL}{product_sopera.pk}/',
            {'base_price': '2800.00'},
            format='json',
        )
        assert res.status_code == 200
        assert res.json()['name'] == original_name

    def test_publicar_producto(self, admin_client, product_sopera, db):
        product_sopera.is_published = False
        product_sopera.save()
        ProductImage.objects.create(
            product=product_sopera, image='products/images/test.jpg',
        )
        res = admin_client.patch(
            f'{ADMIN_PROD_URL}{product_sopera.pk}/',
            {'is_published': True},
            format='json',
        )
        assert res.status_code == 200
        assert res.json()['is_published'] is True

    def test_cambio_categoria_invalida_cache_arbol(
        self, admin_client, product_sopera, cat_pulseras, db
    ):
        """TST-FR-CAT-10.02 Escenario 3: cambio de categoría invalida árbol."""
        cache.set('categories:tree', [{'nombre': 'stale'}], 3600)
        admin_client.patch(
            f'{ADMIN_PROD_URL}{product_sopera.pk}/',
            {'category_ids': [cat_pulseras.pk]},
            format='json',
        )
        assert cache.get('categories:tree') is None

    def test_misma_categoria_no_invalida_cache_arbol(
        self, admin_client, product_sopera, cat_soperas, db
    ):
        """Sin cambio de categoría, el árbol cacheado se conserva."""
        cache.set('categories:tree', [{'nombre': 'valido'}], 3600)
        admin_client.patch(
            f'{ADMIN_PROD_URL}{product_sopera.pk}/',
            {'base_price': '3100.00'},
            format='json',
        )
        # El cache NO debe haberse invalidado (misma categoría)
        assert cache.get('categories:tree') is not None

    def test_desactivar_producto(self, admin_client, product_sopera, db):
        res = admin_client.delete(f'{ADMIN_PROD_URL}{product_sopera.pk}/')
        assert res.status_code == 204
        product_sopera.refresh_from_db()
        assert product_sopera.is_active is False
        assert product_sopera.is_published is False

    def test_sku_duplicado_en_edicion_retorna_409(
        self, admin_client, product_sopera, product_pulsera, db
    ):
        res = admin_client.patch(
            f'{ADMIN_PROD_URL}{product_sopera.pk}/',
            {'sku': product_pulsera.sku},
            format='json',
        )
        assert res.status_code == 409

    def test_br005_precio_cambiado_no_afecta_ordenes_existentes(
        self, admin_client, product_sopera, db
    ):
        """BR-005: snapshot en OrderItem es inmutable frente a cambios de precio en Product."""
        order = Order.objects.create(order_number='PY-BR005TEST')
        OrderItem.objects.create(
            order=order,
            product=product_sopera,
            product_name=product_sopera.name,
            sku=product_sopera.sku,
            unit_price=product_sopera.price,
            quantity=1,
            subtotal=product_sopera.price,
        )
        original_unit_price = product_sopera.price

        res = admin_client.patch(
            f'{ADMIN_PROD_URL}{product_sopera.pk}/',
            {'base_price': '9999.00'},
            format='json',
        )
        assert res.status_code == 200

        item = OrderItem.objects.get(order=order, product=product_sopera)
        assert item.unit_price == original_unit_price
        product_sopera.refresh_from_db()
        assert product_sopera.price == Decimal('9999.00')


# =============================================================================
# Modelo — auto-generación de slug
# =============================================================================

class TestProductAdminSerializerSlug:

    def test_slug_autogenerado_desde_name(self, cat_soperas, db):
        data = {
            'name': 'Collar Oshun Plateado',
            'sku': 'PLT-001',
            'base_price': '1400.00',
            'category_id': cat_soperas.pk,
        }
        s = ProductAdminSerializer(data=data)
        assert s.is_valid(), s.errors
        instance = s.save()
        assert instance.slug == 'collar-oshun-plateado'

    def test_slug_con_colision_agrega_sufijo(self, cat_soperas, db):
        Product.objects.create(
            name='Collar X', slug='collar-x', sku='CX-001',
            description='',
            price=Decimal('100.00'), stock=0,
            is_active=True, is_published=False,
        )
        data = {
            'name': 'Collar X',  # mismo nombre → colisión
            'sku': 'CX-002',
            'base_price': '100.00',
            'category_id': cat_soperas.pk,
        }
        s = ProductAdminSerializer(data=data)
        assert s.is_valid(), s.errors
        instance = s.save()
        assert instance.slug == 'collar-x-1'
