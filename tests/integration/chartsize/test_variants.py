"""
Tests — Product variants (UC-CHT-01/02/03/04)

UC-CHT-01: View variants (variants field in product detail)
UC-CHT-02: Validate variant before adding to cart
UC-CHT-03: Manage variants admin (CRUD)
UC-CHT-04: Variant-specific pricing
"""
import pytest
from decimal import Decimal
from apps.catalogue.models import Category, Product
from apps.chartsize.models import VariantType, VariantOption, ProductVariant

pytestmark = pytest.mark.integration

CATALOGUE_URL  = '/api/v2/products/'
ADMIN_PROD_URL = '/api/v2/admin/products/'


@pytest.fixture
def cat_soperas(db):
    return Category.objects.create(name='Soperas S9', slug='soperas-s9', is_active=True)


@pytest.fixture
def product_s9(db, cat_soperas):
    _p = Product.objects.create(
        name='Sopera Yemaya S9', slug='sopera-s9', sku='S9-YEM-001',
        description='Sopera sagrada',
        price=Decimal('2500.00'), stock=0,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_soperas)
    return _p


@pytest.fixture
def variant_type(db, product_s9):
    return VariantType.objects.create(
        product=product_s9, name='Tamaño', is_active=True, order=0
    )


@pytest.fixture
def opt_chica(db, variant_type):
    return VariantOption.objects.create(
        variant_type=variant_type, label='Chica', slug='chica', order=0, is_active=True
    )


@pytest.fixture
def opt_grande(db, variant_type):
    return VariantOption.objects.create(
        variant_type=variant_type, label='Grande', slug='grande', order=1, is_active=True
    )


@pytest.fixture
def var_chica(db, product_s9, opt_chica):
    return ProductVariant.objects.create(
        product=product_s9, option=opt_chica,
        sku_suffix='CHC', stock=5, is_active=True,
    )


@pytest.fixture
def var_grande(db, product_s9, opt_grande):
    return ProductVariant.objects.create(
        product=product_s9, option=opt_grande,
        sku_suffix='GRD', price_override=Decimal('3500.00'),
        stock=0, is_active=True,
    )


# =============================================================================
# Modelo ProductVariant
# =============================================================================

class TestProductVariantModelo:

    def test_effective_price_sin_override_usa_base(self, var_chica, product_s9, db):
        assert var_chica.effective_price() == product_s9.price

    def test_effective_price_con_override(self, var_grande, db):
        assert var_grande.effective_price() == Decimal('3500.00')

    def test_is_available_con_stock(self, var_chica, db):
        assert var_chica.is_available() is True

    def test_is_available_sin_stock(self, var_grande, db):
        assert var_grande.is_available() is False

    def test_sku_con_sufijo(self, var_chica, product_s9, db):
        assert var_chica.sku == f'{product_s9.sku}-CHC'

    def test_sku_sin_sufijo(self, product_s9, opt_chica, db):
        v = ProductVariant.objects.create(
            product=product_s9, option=opt_chica,
            sku_suffix='', stock=1, is_active=True,
        )
        assert v.sku == product_s9.sku


# =============================================================================
# UC-CHT-01 — Variantes en ficha del producto
# =============================================================================

class TestVariantesEnFicha:

    def test_ficha_incluye_campo_variants(
        self, api_client, product_s9, var_chica, var_grande, db
    ):
        res = api_client.get(f'{CATALOGUE_URL}{product_s9.slug}/')
        assert res.status_code == 200
        assert 'variants' in res.json()

    def test_variants_vacio_sin_variantes(self, api_client, product_s9, db):
        """EX-01: producto sin variantes → variants=[]."""
        res = api_client.get(f'{CATALOGUE_URL}{product_s9.slug}/')
        assert res.json()['variants'] == []

    def test_variants_solo_activas(
        self, api_client, product_s9, var_chica, var_grande, db
    ):
        var_grande.is_active = False
        var_grande.save()
        res = api_client.get(f'{CATALOGUE_URL}{product_s9.slug}/')
        variant_ids = [v['id'] for v in res.json()['variants']]
        assert var_chica.pk in variant_ids
        assert var_grande.pk not in variant_ids

    def test_variant_con_precio_override_muestra_precio_correcto(
        self, api_client, product_s9, var_grande, db
    ):
        var_grande.stock = 2
        var_grande.save()
        res = api_client.get(f'{CATALOGUE_URL}{product_s9.slug}/')
        grande = next(v for v in res.json()['variants'] if v['id'] == var_grande.pk)
        assert Decimal(grande['effective_price']) == Decimal('3500.00')

    def test_variant_sin_stock_no_es_available(
        self, api_client, product_s9, var_grande, db
    ):
        res = api_client.get(f'{CATALOGUE_URL}{product_s9.slug}/')
        grande = next((v for v in res.json()['variants'] if v['id'] == var_grande.pk), None)
        if grande:
            assert grande['is_available'] is False

    def test_variant_tiene_campos_correctos(
        self, api_client, product_s9, var_chica, db
    ):
        res = api_client.get(f'{CATALOGUE_URL}{product_s9.slug}/')
        v = next(v for v in res.json()['variants'] if v['id'] == var_chica.pk)
        for campo in ['id', 'label', 'slug', 'stock', 'is_available',
                      'effective_price', 'price_with_tax']:
            assert campo in v, f'Campo {campo} falta en la respuesta de variante'


# =============================================================================
# UC-CHT-02 — Validacion de variante (endpoint publico)
# =============================================================================

class TestValidacionVariante:

    def test_validar_variante_activa_retorna_200(
        self, api_client, product_s9, var_chica, db
    ):
        res = api_client.get(
            f'{CATALOGUE_URL}{product_s9.slug}/variants/{var_chica.pk}/'
        )
        assert res.status_code == 200
        assert res.json()['is_available'] is True

    def test_validar_variante_inexistente_retorna_404(
        self, api_client, product_s9, db
    ):
        res = api_client.get(
            f'{CATALOGUE_URL}{product_s9.slug}/variants/99999/'
        )
        assert res.status_code == 404

    def test_validar_variante_producto_inactivo_retorna_404(
        self, api_client, product_s9, var_chica, db
    ):
        product_s9.is_active = False
        product_s9.save()
        res = api_client.get(
            f'{CATALOGUE_URL}{product_s9.slug}/variants/{var_chica.pk}/'
        )
        assert res.status_code == 404


# =============================================================================
# UC-CHT-03 — CRUD admin de variantes
# =============================================================================

class TestVariantesAdmin:

    def test_listar_variantes_sin_auth_retorna_401(
        self, api_client, product_s9, db
    ):
        res = api_client.get(
            f'{ADMIN_PROD_URL}{product_s9.pk}/variants/'
        )
        assert res.status_code == 401

    def test_listar_variantes_admin_retorna_200(
        self, admin_client, product_s9, var_chica, db
    ):
        res = admin_client.get(
            f'{ADMIN_PROD_URL}{product_s9.pk}/variants/'
        )
        assert res.status_code == 200
        assert len(res.json()) >= 1

    def test_desactivar_variante_soft_delete(
        self, admin_client, product_s9, var_chica, db
    ):
        res = admin_client.delete(
            f'{ADMIN_PROD_URL}{product_s9.pk}/variants/{var_chica.pk}/'
        )
        assert res.status_code == 204
        var_chica.refresh_from_db()
        assert var_chica.is_active is False
        assert var_chica.stock == 0

    def test_editar_stock_variante(
        self, admin_client, product_s9, var_chica, db
    ):
        res = admin_client.patch(
            f'{ADMIN_PROD_URL}{product_s9.pk}/variants/{var_chica.pk}/',
            {'stock': 15}, format='json'
        )
        assert res.status_code == 200
        var_chica.refresh_from_db()
        assert var_chica.stock == 15


# =============================================================================
# UC-CHT-04 — Precio diferenciado
# =============================================================================

class TestPrecioDiferenciado:

    def test_agregar_precio_override(
        self, admin_client, product_s9, var_chica, db
    ):
        """FR-CHT-04.02: asignar precio diferenciado a una variante."""
        res = admin_client.patch(
            f'{ADMIN_PROD_URL}{product_s9.pk}/variants/{var_chica.pk}/',
            {'price_override': '1800.00'}, format='json'
        )
        assert res.status_code == 200
        var_chica.refresh_from_db()
        assert var_chica.price_override == Decimal('1800.00')

    def test_eliminar_precio_override_vuelve_a_base(
        self, admin_client, product_s9, var_grande, db
    ):
        """Alt-A: eliminar price_override → usa precio base."""
        var_grande.stock = 3
        var_grande.save()
        res = admin_client.patch(
            f'{ADMIN_PROD_URL}{product_s9.pk}/variants/{var_grande.pk}/',
            {'price_override': None}, format='json'
        )
        assert res.status_code == 200
        var_grande.refresh_from_db()
        assert var_grande.price_override is None
        assert var_grande.effective_price() == product_s9.price

    def test_precio_negativo_retorna_400(
        self, admin_client, product_s9, var_chica, db
    ):
        """FR-CHT-04.02: precio diferenciado debe ser > 0."""
        res = admin_client.patch(
            f'{ADMIN_PROD_URL}{product_s9.pk}/variants/{var_chica.pk}/',
            {'price_override': '-50.00'}, format='json'
        )
        assert res.status_code == 400

    def test_precio_cero_retorna_400(
        self, admin_client, product_s9, var_chica, db
    ):
        res = admin_client.patch(
            f'{ADMIN_PROD_URL}{product_s9.pk}/variants/{var_chica.pk}/',
            {'price_override': '0.00'}, format='json'
        )
        assert res.status_code == 400

    def test_precio_inferior_al_base_es_valido(
        self, admin_client, product_s9, var_chica, db
    ):
        """Alt-B: precio menor al base es válido."""
        res = admin_client.patch(
            f'{ADMIN_PROD_URL}{product_s9.pk}/variants/{var_chica.pk}/',
            {'price_override': '1200.00'}, format='json'
        )
        assert res.status_code == 200
