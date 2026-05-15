"""
Tests de integración — Sprint 7
UC-CAT-07: Ver Productos Relacionados
UC-CAT-08: Listar Categorías (Árbol Jerárquico)
UC-CAT-09: Crear Producto (Admin)
UC-CAT-10: Editar Producto (Admin)
"""
import pytest
from decimal import Decimal

pytestmark = pytest.mark.integration

CATALOGUE_URL  = '/api/v1/catalogue/'
CATEGORIES_URL = '/api/v1/catalogue/categories/'
ADMIN_PROD_URL = '/api/v1/admin/products/'


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def cat_soperas(db):
    from apps.catalogue.models import Category
    return Category.objects.create(name='Soperas', slug='soperas', is_active=True)


@pytest.fixture
def cat_soperas_grandes(db, cat_soperas):
    from apps.catalogue.models import Category
    return Category.objects.create(
        name='Soperas Grandes', slug='soperas-grandes',
        parent=cat_soperas, is_active=True,
    )


@pytest.fixture
def cat_pulseras(db):
    from apps.catalogue.models import Category
    return Category.objects.create(name='Pulseras', slug='pulseras', is_active=True)


@pytest.fixture
def product_sopera(db, cat_soperas):
    from apps.catalogue.models import Product
    return Product.objects.create(
        name='Sopera Yemaya', slug='sopera-yemaya', sku='SOP-YEM-001',
        description='Sopera sagrada de Yemaya', category=cat_soperas,
        price=Decimal('3200.00'), stock=2,
        is_active=True, is_published=True,
    )


@pytest.fixture
def products_soperas(db, cat_soperas):
    """5 productos en cat_soperas para testear related."""
    from apps.catalogue.models import Product
    prods = []
    for i in range(5):
        prods.append(Product.objects.create(
            name=f'Sopera Orisha {i}', slug=f'sopera-orisha-{i}', sku=f'SOP-{i:03}',
            description='', category=cat_soperas,
            price=Decimal('2000.00'), stock=1,
            is_active=True, is_published=True,
        ))
    return prods


@pytest.fixture
def product_pulsera(db, cat_pulseras):
    from apps.catalogue.models import Product
    return Product.objects.create(
        name='Pulsera Elegua', slug='pulsera-elegua-s7', sku='PUL-ELE-001',
        description='Pulsera sagrada de Elegua', category=cat_pulseras,
        price=Decimal('480.00'), stock=10,
        is_active=True, is_published=True,
    )


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
        """Solo productos de la misma categoría."""
        res = api_client.get(f'{CATALOGUE_URL}{product_sopera.slug}/')
        related_slugs = [p['slug'] for p in res.json()['related_products']]
        assert product_pulsera.slug not in related_slugs

    def test_relacionados_vacios_cuando_es_unico(
        self, api_client, product_sopera, db
    ):
        """TST-FR-CAT-07.02 Escenario 3: sin relacionados = lista vacía."""
        res = api_client.get(f'{CATALOGUE_URL}{product_sopera.slug}/')
        assert res.json()['related_products'] == []

    def test_relacionados_hasta_4_aunque_haya_mas(
        self, api_client, product_sopera, products_soperas, db
    ):
        """Máximo 4 aunque haya más disponibles."""
        res = api_client.get(f'{CATALOGUE_URL}{product_sopera.slug}/')
        assert len(res.json()['related_products']) <= 4

    def test_relacionados_tienen_campos_correctos(
        self, api_client, product_sopera, products_soperas, db
    ):
        res = api_client.get(f'{CATALOGUE_URL}{product_sopera.slug}/')
        if res.json()['related_products']:
            item = res.json()['related_products'][0]
            assert 'id' in item
            assert 'name' in item
            assert 'slug' in item
            assert 'base_price' in item
            assert 'price_with_tax' in item


# =============================================================================
# UC-CAT-08 — Árbol de categorías (TST-FR-CAT-08.02)
# =============================================================================

class TestArbolCategorias:

    def test_arbol_retorna_200_sin_autenticar(self, api_client, db):
        res = api_client.get(CATEGORIES_URL)
        assert res.status_code == 200

    def test_arbol_incluye_categorias_activas(
        self, api_client, cat_soperas, cat_pulseras, db
    ):
        res = api_client.get(CATEGORIES_URL)
        names = [c['name'] for c in res.json()]
        assert 'Soperas' in names
        assert 'Pulseras' in names

    def test_arbol_excluye_categorias_inactivas(
        self, api_client, cat_soperas, db
    ):
        cat_soperas.is_active = False
        cat_soperas.save()
        res = api_client.get(CATEGORIES_URL)
        names = [c['name'] for c in res.json()]
        assert 'Soperas' not in names

    def test_arbol_incluye_subcategorias(
        self, api_client, cat_soperas, cat_soperas_grandes, db
    ):
        res = api_client.get(CATEGORIES_URL)
        soperas = next(c for c in res.json() if c['name'] == 'Soperas')
        children_names = [c['name'] for c in soperas['children']]
        assert 'Soperas Grandes' in children_names

    def test_arbol_product_count_correcto(
        self, api_client, cat_soperas, product_sopera, db
    ):
        """TST-FR-CAT-08.02 Escenario 3: product_count = activos y publicados."""
        from apps.catalogue.models import Product
        # Crear uno inactivo que no debe contar
        Product.objects.create(
            name='Inactiva', slug='sop-inact', sku='INV-001',
            description='', category=cat_soperas,
            price=Decimal('100.00'), stock=0,
            is_active=False, is_published=True,
        )
        res = api_client.get(CATEGORIES_URL)
        soperas = next(c for c in res.json() if c['name'] == 'Soperas')
        assert soperas['product_count'] == 1  # solo product_sopera (activo)

    def test_arbol_product_count_acumula_descendientes(
        self, api_client, cat_soperas, cat_soperas_grandes, product_sopera, db
    ):
        """product_count del padre incluye productos de sus subcategorías."""
        from apps.catalogue.models import Product
        Product.objects.create(
            name='Sopera Grande Shango', slug='sop-grande-shn', sku='SOP-GRD-001',
            description='', category=cat_soperas_grandes,
            price=Decimal('5000.00'), stock=1,
            is_active=True, is_published=True,
        )
        res = api_client.get(CATEGORIES_URL)
        soperas_node = next(c for c in res.json() if c['name'] == 'Soperas')
        # product_sopera en padre + Sopera Grande en hijo = 2 total
        assert soperas_node['product_count'] == 2

    def test_arbol_usa_cache(self, api_client, cat_soperas, db):
        """TST-FR-CAT-08.02 Escenario 1: segunda llamada viene del cache."""
        from django.core.cache import cache
        api_client.get(CATEGORIES_URL)
        cached = cache.get('categories:tree')
        assert cached is not None
        # Segunda llamada — mismo resultado
        res2 = api_client.get(CATEGORIES_URL)
        assert res2.status_code == 200

    def test_crear_categoria_invalida_cache_del_arbol(
        self, admin_client, cat_soperas, db
    ):
        """TST-FR-CAT-08.02 Escenario 2: modificación invalida cache."""
        from django.core.cache import cache
        cache.set('categories:tree', [{'nombre': 'stale'}], 3600)
        admin_client.post('/api/v1/admin/categories/', {
            'name': 'Nueva Categoria Sprint7', 'slug': 'nueva-cat-s7',
        }, format='json')
        assert cache.get('categories:tree') is None

    def test_estructura_respuesta_tiene_campos_correctos(
        self, api_client, cat_soperas, db
    ):
        res = api_client.get(CATEGORIES_URL)
        cat = res.json()[0]
        assert 'id' in cat
        assert 'name' in cat
        assert 'slug' in cat
        assert 'product_count' in cat
        assert 'children' in cat


# =============================================================================
# UC-CAT-09 — Crear producto admin (TST-FR-CAT-09.02)
# =============================================================================

class TestCrearProductoAdmin:

    def test_crear_producto_sin_auth_retorna_401(self, api_client, db):
        res = api_client.post(ADMIN_PROD_URL, {}, format='json')
        assert res.status_code == 401

    def test_crear_producto_usuario_normal_retorna_403(
        self, auth_client, db
    ):
        res = auth_client.post(ADMIN_PROD_URL, {}, format='json')
        assert res.status_code == 403

    def test_crear_producto_minimo_exitoso(self, admin_client, cat_soperas, db):
        """TST-FR-CAT-09.02 Escenario 1: producto creado con is_published=False."""
        res = admin_client.post(ADMIN_PROD_URL, {
            'name': 'Collar Ogun nuevo',
            'sku':  'OGN-001',
            'category_id': cat_soperas.pk,
            'base_price': '950.00',
        }, format='json')
        assert res.status_code == 201
        data = res.json()
        assert data['name'] == 'Collar Ogun nuevo'
        assert data['is_published'] is False  # borrador por defecto

    def test_crear_producto_auto_genera_slug(self, admin_client, cat_soperas, db):
        res = admin_client.post(ADMIN_PROD_URL, {
            'name': 'Brazalete Yemaya Dorado',
            'sku':  'BRZ-YEM-001',
            'category_id': cat_soperas.pk,
            'base_price': '720.00',
        }, format='json')
        assert res.status_code == 201
        assert res.json()['slug'] == 'brazalete-yemaya-dorado'

    def test_crear_producto_sku_duplicado_retorna_400(
        self, admin_client, cat_soperas, product_sopera, db
    ):
        """TST-FR-CAT-09.02 Escenario 2: SKU duplicado."""
        res = admin_client.post(ADMIN_PROD_URL, {
            'name': 'Otro Producto',
            'sku':  product_sopera.sku,  # mismo SKU
            'category_id': cat_soperas.pk,
            'base_price': '100.00',
        }, format='json')
        assert res.status_code == 400

    def test_crear_producto_categoria_inexistente_retorna_400(
        self, admin_client, db
    ):
        res = admin_client.post(ADMIN_PROD_URL, {
            'name': 'Test', 'sku': 'TST-999',
            'category_id': 99999,
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
        from django.core.cache import cache
        cache.set('categories:tree', [{'nombre': 'stale'}], 3600)
        admin_client.patch(
            f'{ADMIN_PROD_URL}{product_sopera.pk}/',
            {'category_id': cat_pulseras.pk},
            format='json',
        )
        assert cache.get('categories:tree') is None

    def test_misma_categoria_no_invalida_cache_arbol(
        self, admin_client, product_sopera, cat_soperas, db
    ):
        """Sin cambio de categoría, el árbol cacheado se conserva."""
        from django.core.cache import cache
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

    def test_sku_duplicado_en_edicion_retorna_400(
        self, admin_client, product_sopera, product_pulsera, db
    ):
        res = admin_client.patch(
            f'{ADMIN_PROD_URL}{product_sopera.pk}/',
            {'sku': product_pulsera.sku},
            format='json',
        )
        assert res.status_code == 400

    def test_br005_precio_cambiado_no_afecta_ordenes_existentes(
        self, admin_client, product_sopera, db
    ):
        """BR-005: sin apps.orders en Sprint 7 — verificar solo que el endpoint funcione."""
        res = admin_client.patch(
            f'{ADMIN_PROD_URL}{product_sopera.pk}/',
            {'base_price': '9999.00'},
            format='json',
        )
        assert res.status_code == 200
        # No hay orders que verificar — el snapshot se verifica en Sprint 18


# =============================================================================
# Modelo — auto-generación de slug
# =============================================================================

class TestProductAdminSerializerSlug:

    def test_slug_autogenerado_desde_name(self, cat_soperas, db):
        from apps.catalogue.serializers import ProductAdminSerializer
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
        from apps.catalogue.models import Product
        from apps.catalogue.serializers import ProductAdminSerializer
        Product.objects.create(
            name='Collar X', slug='collar-x', sku='CX-001',
            description='', category=cat_soperas,
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
