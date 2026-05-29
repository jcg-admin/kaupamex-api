"""
Tests — Search history, autocomplete and catalogue filters

UC-SRCH-02: Autocomplete / suggestions
UC-SRCH-03: Save search history
UC-CAT-04: Filter catalogue by category (with subcategories)
UC-CAT-05: Filter catalogue by price range
UC-CAT-06: Manage catalogue categories (admin)
"""
import pytest
from decimal import Decimal
from apps.catalogue.models import Category, Product, SearchHistory
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.cache import cache
import time

pytestmark = pytest.mark.integration

CATALOGUE_URL    = '/api/v1/catalogue/'
AUTOCOMPLETE_URL = '/api/v1/catalogue/autocomplete/'
SEARCH_URL       = '/api/v1/catalogue/search/'
HISTORY_URL      = '/api/v1/catalogue/search/history/'
CATEGORIES_URL   = '/api/v1/admin/categories/'


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def cat_collares(db):
    return Category.objects.create(name='Collares', slug='collares', is_active=True)


@pytest.fixture
def cat_collares_oshun(db, cat_collares):
    return Category.objects.create(
        name='Collares de Oshun', slug='collares-oshun',
        parent=cat_collares, is_active=True,
    )


@pytest.fixture
def cat_pulseras(db):
    return Category.objects.create(name='Pulseras', slug='pulseras', is_active=True)


@pytest.fixture
def product_collar(db, cat_collares):
    _p = Product.objects.create(
        name='Collar Yemaya', slug='collar-yemaya', sku='YEM-001',
        description='Collar sagrado',
        price=Decimal('1200.00'), stock=5,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_collares)
    return _p


@pytest.fixture
def product_collar_oshun(db, cat_collares_oshun):
    _p = Product.objects.create(
        name='Collar Oshun dorado', slug='collar-oshun-dorado', sku='OSH-001',
        description='Collar de Oshun',
        price=Decimal('1500.00'), stock=3,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_collares_oshun)
    return _p


@pytest.fixture
def product_pulsera(db, cat_pulseras):
    _p = Product.objects.create(
        name='Pulsera Elegua', slug='pulsera-elegua', sku='ELE-001',
        description='Pulsera de Elegua',
        price=Decimal('450.00'), stock=10,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_pulseras)
    return _p


@pytest.fixture
def auth_client_user(api_client, user):
    """Cliente autenticado con JWT — comprador regular."""
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


# =============================================================================
# UC-SRCH-02 — Autocomplete (TST-FR-SRCH-02.01)
# =============================================================================

class TestAutocomplete:

    def test_autocomplete_retorna_200_sin_autenticar(self, api_client, db):
        res = api_client.get(AUTOCOMPLETE_URL, {'q': 'co'})
        assert res.status_code == 200

    def test_autocomplete_retorna_lista_vacia_si_prefijo_corto(self, api_client, db):
        res = api_client.get(AUTOCOMPLETE_URL, {'q': 'c'})
        assert res.status_code == 200
        assert res.json() == []

    def test_autocomplete_retorna_productos_por_prefijo(
        self, api_client, product_collar, product_pulsera, db
    ):
        res = api_client.get(AUTOCOMPLETE_URL, {'q': 'colla'})
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 1
        assert any(p['name'] == 'Collar Yemaya' for p in data)

    def test_autocomplete_no_incluye_no_publicados(self, api_client, cat_collares, db):
        Product.objects.create(
            name='Collar Secreto', slug='collar-secreto', sku='SEC-001',
            description='',
            price=Decimal('100.00'), stock=1,
            is_active=True, is_published=False,
        )
        res = api_client.get(AUTOCOMPLETE_URL, {'q': 'Collar S'})
        slugs = [p['slug'] for p in res.json()]
        assert 'collar-secreto' not in slugs

    def test_autocomplete_max_5_resultados(self, api_client, cat_collares, db):
        for i in range(8):
            Product.objects.create(
                name=f'Collar Extra {i}', slug=f'collar-extra-{i}', sku=f'EXT-{i:03}',
                description='', price=Decimal('100.00'),
                stock=1, is_active=True, is_published=True,
            )
        res = api_client.get(AUTOCOMPLETE_URL, {'q': 'Collar'})
        assert len(res.json()) <= 5

    def test_autocomplete_usa_cache(self, api_client, product_collar, db):
        """TST-FR-SRCH-02.01 Escenario 2: segunda llamada viene del cache."""
        # Primer request — llena cache
        api_client.get(AUTOCOMPLETE_URL, {'q': 'Collar'})
        cache_key = 'autocomplete:collar'
        cached = cache.get(cache_key)
        assert cached is not None, "El cache debe haberse llenado tras el primer request"
        # Segundo request — mismo resultado
        res2 = api_client.get(AUTOCOMPLETE_URL, {'q': 'Collar'})
        assert res2.status_code == 200

    def test_autocomplete_retorna_campos_correctos(self, api_client, product_collar, db):
        res = api_client.get(AUTOCOMPLETE_URL, {'q': 'Collar'})
        item = res.json()[0]
        assert 'id' in item
        assert 'name' in item
        assert 'slug' in item


# =============================================================================
# UC-SRCH-03 — Historial de búsquedas (TST-FR-SRCH-03.01)
# =============================================================================

class TestSearchHistory:

    def test_historial_requiere_autenticacion(self, api_client, db):
        res = api_client.get(HISTORY_URL)
        assert res.status_code == 401

    def test_historial_vacio_inicial(self, auth_client_user, db):
        res = auth_client_user.get(HISTORY_URL)
        assert res.status_code == 200
        assert res.json() == []

    def test_busqueda_guarda_historial_para_autenticado(
        self, auth_client_user, product_collar, db
    ):
        """TST-FR-SRCH-03.01 Escenario 1: término nuevo se crea."""
        auth_client_user.get(SEARCH_URL, {'q': 'collar sagrado'})
        # Esperar al hilo de threading
        time.sleep(0.3)
        res = auth_client_user.get(HISTORY_URL)
        terms = [e['term'] for e in res.json()]
        assert 'collar sagrado' in terms

    def test_busqueda_no_guarda_historial_para_anonimo(
        self, api_client, product_collar, db
    ):
        api_client.get(SEARCH_URL, {'q': 'collar'})
        assert SearchHistory.objects.count() == 0

    def test_historial_upsert_no_duplica(self, auth_client_user, user, db):
        """TST-FR-SRCH-03.01 Escenario 2: término repetido — upsert."""
        SearchHistory.record(user=user, term='collar')
        SearchHistory.record(user=user, term='collar')
        assert SearchHistory.objects.filter(user=user, term='collar').count() == 1

    def test_historial_trim_a_20_entradas(self, user, db):
        """TST-FR-SRCH-03.01 Escenario 3: trim automático."""
        for i in range(22):
            SearchHistory.objects.update_or_create(
                user=user, term=f'termino-{i}', defaults={}
            )
        SearchHistory.record(user=user, term='nuevo-termino')
        assert SearchHistory.objects.filter(user=user).count() <= 20

    def test_borrar_entrada_individual(self, auth_client_user, user, db):
        entry = SearchHistory.objects.create(user=user, term='oshun')
        res = auth_client_user.delete(f'{HISTORY_URL}{entry.pk}/')
        assert res.status_code == 204
        assert not SearchHistory.objects.filter(pk=entry.pk).exists()

    def test_borrar_entrada_de_otro_usuario_retorna_404(
        self, auth_client_user, admin_user, db
    ):
        entry = SearchHistory.objects.create(user=admin_user, term='elegua')
        res = auth_client_user.delete(f'{HISTORY_URL}{entry.pk}/')
        assert res.status_code == 404

    def test_borrar_todo_el_historial(self, auth_client_user, user, db):
        SearchHistory.objects.create(user=user, term='a')
        SearchHistory.objects.create(user=user, term='b')
        res = auth_client_user.delete(HISTORY_URL)
        assert res.status_code == 204
        assert SearchHistory.objects.filter(user=user).count() == 0

    def test_historial_ordenado_por_mas_reciente(self, auth_client_user, user, db):
        SearchHistory.objects.create(user=user, term='primero')
        SearchHistory.objects.create(user=user, term='segundo')
        res = auth_client_user.get(HISTORY_URL)
        terms = [e['term'] for e in res.json()]
        assert terms.index('segundo') < terms.index('primero')


# =============================================================================
# UC-CAT-04 — Filtrar por categoría con subcategorías
# =============================================================================

class TestFiltroPorCategoria:

    def test_filtro_categoria_incluye_subcategorias(
        self, api_client, product_collar, product_collar_oshun,
        cat_collares, cat_collares_oshun, db
    ):
        """
        Filtrar por 'collares' debe incluir productos de 'collares'
        y de 'collares-oshun' (subcategoría). FR-CAT-04.02 Escenario 1.
        """
        res = api_client.get(CATALOGUE_URL, {'category': 'collares'})
        assert res.status_code == 200
        slugs = [p['slug'] for p in res.json()['results']]
        assert 'collar-yemaya' in slugs
        assert 'collar-oshun-dorado' in slugs

    def test_filtro_categoria_sin_subcategorias_exacto(
        self, api_client, product_collar, product_collar_oshun,
        cat_collares_oshun, db
    ):
        """
        Filtrar por 'collares-oshun' (hoja) solo incluye sus productos.
        FR-CAT-04.02 Escenario 2.
        """
        res = api_client.get(CATALOGUE_URL, {'category': 'collares-oshun'})
        slugs = [p['slug'] for p in res.json()['results']]
        assert 'collar-oshun-dorado' in slugs
        assert 'collar-yemaya' not in slugs

    def test_filtro_categoria_inexistente_retorna_vacio(self, api_client, db):
        res = api_client.get(CATALOGUE_URL, {'category': 'no-existe'})
        assert res.status_code == 200
        assert res.json()['count'] == 0

    def test_filtro_categoria_inactiva_retorna_vacio(
        self, api_client, cat_collares, product_collar, db
    ):
        cat_collares.is_active = False
        cat_collares.save()
        res = api_client.get(CATALOGUE_URL, {'category': 'collares'})
        assert res.json()['count'] == 0

    def test_filtro_no_afecta_otros_subdominios(
        self, api_client, product_collar, product_pulsera, db
    ):
        res = api_client.get(CATALOGUE_URL, {'category': 'collares'})
        slugs = [p['slug'] for p in res.json()['results']]
        assert 'pulsera-elegua' not in slugs


# =============================================================================
# UC-CAT-05 — Filtrar por rango de precio
# =============================================================================

class TestFiltroPorPrecio:

    def test_price_min_filtra_productos_caros(
        self, api_client, product_collar, product_pulsera, db
    ):
        # collar=1200, pulsera=450 — price_min=1000
        res = api_client.get(CATALOGUE_URL, {'price_min': '1000'})
        slugs = [p['slug'] for p in res.json()['results']]
        assert 'collar-yemaya' in slugs
        assert 'pulsera-elegua' not in slugs

    def test_price_max_filtra_productos_baratos(
        self, api_client, product_collar, product_pulsera, db
    ):
        # collar=1200, pulsera=450 — price_max=500
        res = api_client.get(CATALOGUE_URL, {'price_max': '500'})
        slugs = [p['slug'] for p in res.json()['results']]
        assert 'pulsera-elegua' in slugs
        assert 'collar-yemaya' not in slugs

    def test_price_min_y_max_rango(
        self, api_client, product_collar, product_pulsera, db
    ):
        res = api_client.get(CATALOGUE_URL, {'price_min': '400', 'price_max': '600'})
        slugs = [p['slug'] for p in res.json()['results']]
        assert 'pulsera-elegua' in slugs
        assert 'collar-yemaya' not in slugs

    def test_price_invalido_retorna_400(self, api_client, db):
        res = api_client.get(CATALOGUE_URL, {'price_min': 'no-es-numero'})
        assert res.status_code == 400

    def test_rango_sin_resultados_retorna_vacio(
        self, api_client, product_collar, db
    ):
        res = api_client.get(CATALOGUE_URL, {'price_min': '99999'})
        assert res.json()['count'] == 0

    def test_filtros_precio_y_categoria_combinados(
        self, api_client, product_collar, product_collar_oshun,
        product_pulsera, db
    ):
        # collar_yemaya=1200 en 'collares', collar_oshun=1500 en 'collares-oshun'
        # price_max=1300 + category=collares → solo collar_yemaya
        res = api_client.get(CATALOGUE_URL, {
            'category': 'collares', 'price_max': '1300'
        })
        slugs = [p['slug'] for p in res.json()['results']]
        assert 'collar-yemaya' in slugs
        assert 'collar-oshun-dorado' not in slugs
        assert 'pulsera-elegua' not in slugs


# =============================================================================
# UC-CAT-06 — Gestionar Categorías (Admin CRUD)
# =============================================================================

class TestCategoryAdmin:

    def test_listar_categorias_sin_auth_retorna_401(self, api_client, db):
        res = api_client.get(CATEGORIES_URL)
        assert res.status_code == 401

    def test_listar_categorias_usuario_normal_retorna_403(
        self, auth_client_user, db
    ):
        res = auth_client_user.get(CATEGORIES_URL)
        assert res.status_code == 403

    def test_listar_categorias_admin_retorna_200(self, admin_client, db):
        res = admin_client.get(CATEGORIES_URL)
        assert res.status_code == 200

    def test_crear_categoria_raiz(self, admin_client, db):
        res = admin_client.post(CATEGORIES_URL, {
            'name': 'Soperas', 'slug': 'soperas', 'description': 'Soperas sagradas',
        }, format='json')
        assert res.status_code == 201
        assert res.json()['name'] == 'Soperas'

    def test_crear_categoria_con_padre(self, admin_client, cat_collares, db):
        res = admin_client.post(CATEGORIES_URL, {
            'name': 'Collares de Shango', 'slug': 'collares-shango',
            'parent_id': cat_collares.pk,
        }, format='json')
        assert res.status_code == 201
        assert res.json()['parent_id'] == cat_collares.pk

    def test_editar_categoria(self, admin_client, cat_collares, db):
        res = admin_client.patch(
            f'{CATEGORIES_URL}{cat_collares.pk}/',
            {'description': 'Collares sagrados actualizados'},
            format='json',
        )
        assert res.status_code == 200
        assert 'actualizados' in res.json()['description']

    def test_desactivar_categoria_sin_productos(self, admin_client, cat_collares, db):
        res = admin_client.delete(f'{CATEGORIES_URL}{cat_collares.pk}/')
        assert res.status_code == 204
        cat_collares.refresh_from_db()
        assert cat_collares.is_active is False

    def test_desactivar_categoria_endpoint_explicito(
        self, admin_client, cat_collares, db,
    ):
        """T-109-A iter 18 (UC-CAT-06 D-01 CRITICA): endpoint
        ``POST .../deactivate/`` que la UI invoca. Antes solo existia
        DELETE -> UI recibia 405."""
        res = admin_client.post(f'{CATEGORIES_URL}{cat_collares.pk}/deactivate/')
        assert res.status_code == 200, res.content
        cat_collares.refresh_from_db()
        assert cat_collares.is_active is False

    def test_desactivar_endpoint_con_productos_retorna_400(
        self, admin_client, cat_collares, product_collar, db,
    ):
        """T-109-A: el endpoint explicito hereda la misma logica de
        FR-CAT-06.02 (rechazo con productos activos)."""
        res = admin_client.post(f'{CATEGORIES_URL}{cat_collares.pk}/deactivate/')
        assert res.status_code == 400
        assert 'CATEGORY_HAS_PRODUCTS' in str(res.json())

    def test_desactivar_categoria_con_productos_retorna_400(
        self, admin_client, cat_collares, product_collar, db
    ):
        """FR-CAT-06.02 Escenario 3: no se puede desactivar con productos activos."""
        res = admin_client.delete(f'{CATEGORIES_URL}{cat_collares.pk}/')
        assert res.status_code == 400
        # T-109-B anti-soft-on-tests (canon EN).
        assert 'CATEGORY_HAS_PRODUCTS' in str(res.json())

    def test_ciclo_directo_retorna_400(
        self, admin_client, cat_collares, cat_collares_oshun, db
    ):
        """
        FR-CAT-06.02 Escenario 2: A es padre de B → no se puede hacer B padre de A.
        cat_collares es padre de cat_collares_oshun.
        Intentar hacer cat_collares_oshun padre de cat_collares = ciclo.
        """
        res = admin_client.patch(
            f'{CATEGORIES_URL}{cat_collares.pk}/',
            {'parent_id': cat_collares_oshun.pk},
            format='json',
        )
        assert res.status_code == 400
        # T-109-B anti-soft-on-tests (canon EN).
        assert 'CYCLE_IN_HIERARCHY' in str(res.json())

    def test_nombre_duplicado_retorna_400(self, admin_client, cat_collares, db):
        res = admin_client.post(CATEGORIES_URL, {
            'name': 'Collares', 'slug': 'collares-2',
        }, format='json')
        assert res.status_code == 400

    def test_crear_categoria_invalida_cache(self, admin_client, db):
        """FR-CAT-06.02: cualquier mutación invalida el cache categories:tree."""
        cache.set('categories:tree', {'dummy': True}, 300)
        admin_client.post(CATEGORIES_URL, {
            'name': 'Nueva Cat', 'slug': 'nueva-cat',
        }, format='json')
        assert cache.get('categories:tree') is None


# =============================================================================
# Modelo Category — método would_create_cycle
# =============================================================================

class TestCategoryModel:

    def test_sin_padre_no_crea_ciclo(self, cat_collares, db):
        assert cat_collares.would_create_cycle(None) is False

    def test_asignarse_a_si_mismo_como_padre_crea_ciclo(self, cat_collares, db):
        assert cat_collares.would_create_cycle(cat_collares) is True

    def test_descendiente_como_padre_crea_ciclo(
        self, cat_collares, cat_collares_oshun, db
    ):
        # collares es padre de collares_oshun
        # Intentar hacer collares_oshun padre de collares = ciclo
        assert cat_collares.would_create_cycle(cat_collares_oshun) is True

    def test_categoria_hermana_no_crea_ciclo(
        self, cat_collares, cat_pulseras, db
    ):
        assert cat_collares.would_create_cycle(cat_pulseras) is False

    def test_get_descendants_pks_incluye_hijos(
        self, cat_collares, cat_collares_oshun, db
    ):
        pks = cat_collares.get_descendants_ids()
        assert cat_collares.pk in pks
        assert cat_collares_oshun.pk in pks

    def test_get_descendants_pks_categoria_hoja(self, cat_collares_oshun, db):
        pks = cat_collares_oshun.get_descendants_ids()
        assert pks == {cat_collares_oshun.pk}
