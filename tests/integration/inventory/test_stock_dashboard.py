"""
Tests — Stock dashboard, decrement and configuration

UC-INV-01: Stock dashboard
UC-INV-02: Stock decrement (InventoryService)
UC-INV-04: Manual stock adjustment
UC-CFG-04: Static content (StaticPage/Version)
UC-CFG-05: Contact data (SiteSettings extended)
"""
import pytest
from decimal import Decimal
from apps.catalogue.models import Category, Product
from apps.chartsize.models import VariantType, VariantOption, ProductVariant
from apps.settings_app.models import StaticPageVersion, SiteSettings
from apps.inventory.services import InventoryService, InsufficientStockError
from apps.inventory.models import StockAlert

pytestmark = pytest.mark.integration

INV_URL      = '/api/v2/admin/inventory/'
ALERTS_URL   = '/api/v2/admin/inventory/alerts/'
SETTINGS_URL = '/api/v1/config/settings/'
PAGES_URL    = '/api/v1/admin/pages/'


@pytest.fixture
def cat_s10(db):
    return Category.objects.create(name='Cat S10', slug='cat-s10', is_active=True)


@pytest.fixture
def product_s10(db, cat_s10):
    _p = Product.objects.create(
        name='Prod S10', slug='prod-s10', sku='S10-001',
        description='',
        price=Decimal('500.00'), stock=10,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_s10)
    return _p


@pytest.fixture
def variant_type_s10(db, product_s10):
    return VariantType.objects.create(
        product=product_s10, name='Tamaño S10', order=0
    )


@pytest.fixture
def opt_s10(db, variant_type_s10):
    return VariantOption.objects.create(
        variant_type=variant_type_s10, label='Mediana', slug='mediana-s10', order=0
    )


@pytest.fixture
def variant_s10(db, product_s10, opt_s10):
    return ProductVariant.objects.create(
        product=product_s10, option=opt_s10,
        sku_suffix='MED', stock=8, is_active=True,
    )


# =============================================================================
# UC-CFG-05 — Datos de contacto en SiteSettings
# =============================================================================

class TestDatosContacto:

    def test_patch_email_soporte(self, admin_client, db):
        res = admin_client.patch(SETTINGS_URL,
            {'support_email': 'soporte@practicayoruba.mx'}, format='json')
        assert res.status_code == 200

    def test_patch_telefono(self, admin_client, db):
        res = admin_client.patch(SETTINGS_URL, {'phone': '+52 55 1234 5678'}, format='json')
        assert res.status_code == 200

    def test_patch_redes_sociales(self, admin_client, db):
        res = admin_client.patch(SETTINGS_URL, {
            'social_links': {'instagram': 'https://instagram.com/practicayoruba'}
        }, format='json')
        assert res.status_code == 200
        assert 'instagram' in res.json()['social_links']

    def test_campos_contacto_en_serializer(self, admin_client, db):
        res = admin_client.get(SETTINGS_URL)
        data = res.json()
        for campo in ['support_email', 'phone', 'address', 'social_links']:
            assert campo in data, f'{campo} falta en la respuesta'


# =============================================================================
# UC-CFG-04 — Contenido estático
# =============================================================================

class TestContenidoEstatico:

    def test_listar_paginas_sin_auth_retorna_401(self, api_client, db):
        res = api_client.get(PAGES_URL)
        assert res.status_code == 401

    def test_publicar_pagina_crea_version(self, admin_client, db):
        res = admin_client.post(f'{PAGES_URL}about/publish/', {
            'content': '<h1>Sobre nosotros</h1><p>Yoruba desde 2024.</p>'
        }, format='json')
        assert res.status_code == 201
        data = res.json()
        assert data['version'] == 1
        assert data['status'] == 'PUBLISHED'

    def test_segunda_publicacion_incrementa_version(self, admin_client, db):
        admin_client.post(f'{PAGES_URL}about/publish/',
            {'content': 'v1'}, format='json')
        res = admin_client.post(f'{PAGES_URL}about/publish/',
            {'content': 'v2'}, format='json')
        assert res.json()['version'] == 2

    def test_segunda_publicacion_archiva_anterior(self, admin_client, db):
        admin_client.post(f'{PAGES_URL}terms/publish/',
            {'content': 'v1'}, format='json')
        admin_client.post(f'{PAGES_URL}terms/publish/',
            {'content': 'v2'}, format='json')
        archived = StaticPageVersion.objects.filter(
            page__slug='terms', status='ARCHIVED'
        )
        assert archived.count() == 1

    def test_revertir_a_version_anterior(self, admin_client, db):
        admin_client.post(f'{PAGES_URL}faq/publish/', {'content': 'v1'}, format='json')
        admin_client.post(f'{PAGES_URL}faq/publish/', {'content': 'v2'}, format='json')
        res = admin_client.post(f'{PAGES_URL}faq/versions/1/restore/')
        assert res.status_code == 201
        assert res.json()['version'] == 3
        assert res.json()['status'] == 'PUBLISHED'

    def test_ver_pagina_con_version_actual(self, admin_client, db):
        admin_client.post(f'{PAGES_URL}privacy/publish/',
            {'content': 'Privacidad'}, format='json')
        res = admin_client.get(f'{PAGES_URL}privacy/')
        assert res.status_code == 200
        assert res.json()['current_version']['content'] == 'Privacidad'

    def test_pagina_inexistente_retorna_404(self, admin_client, db):
        res = admin_client.get(f'{PAGES_URL}no-existe/')
        assert res.status_code == 404


# =============================================================================
# UC-INV-01 — Dashboard de inventario
# =============================================================================

class TestDashboardInventario:

    def test_dashboard_sin_auth_retorna_401(self, api_client, db):
        res = api_client.get(INV_URL)
        assert res.status_code == 401

    def test_dashboard_admin_retorna_200(self, admin_client, db):
        res = admin_client.get(INV_URL)
        assert res.status_code == 200

    def test_dashboard_incluye_estado_normal(
        self, admin_client, product_s10, db
    ):
        res = admin_client.get(INV_URL)
        # product_s10 tiene stock=10, umbral default=5 → NORMAL
        skus = [r['sku'] for r in res.json()['results']]
        assert product_s10.sku in skus
        item = next(r for r in res.json()['results'] if r['sku'] == product_s10.sku)
        assert item['status'] == 'NORMAL'

    def test_dashboard_producto_con_variante(
        self, admin_client, product_s10, variant_s10, db
    ):
        res = admin_client.get(INV_URL)
        items = [r for r in res.json()['results']
                 if r['variant_id'] == variant_s10.pk]
        assert len(items) == 1
        assert items[0]['stock'] == 8

    def test_filtro_por_estado_bajo(
        self, admin_client, product_s10, variant_s10, db
    ):
        variant_s10.stock = 2
        variant_s10.save()
        res = admin_client.get(INV_URL, {'status': 'BAJO'})
        statuses = {r['status'] for r in res.json()['results']}
        assert statuses <= {'BAJO'}

    def test_filtro_por_estado_agotado(
        self, admin_client, product_s10, variant_s10, db
    ):
        variant_s10.stock = 0
        variant_s10.save()
        res = admin_client.get(INV_URL, {'status': 'AGOTADO'})
        for r in res.json()['results']:
            assert r['status'] == 'AGOTADO'


# =============================================================================
# UC-INV-02 / InventoryService — Decremento de stock
# =============================================================================

class TestInventoryServiceDecrement:

    def test_decremento_simple_sin_variante(self, product_s10, db):
        product_s10.stock = 10
        product_s10.save()
        movs = InventoryService.decrement(
            [{'product': product_s10, 'variant': None, 'quantity': 3}]
        )
        assert len(movs) == 1
        product_s10.refresh_from_db()
        assert product_s10.stock == 7

    def test_decremento_con_variante(self, product_s10, variant_s10, db):
        variant_s10.stock = 8
        variant_s10.save()
        movs = InventoryService.decrement(
            [{'product': product_s10, 'variant': variant_s10, 'quantity': 2}]
        )
        variant_s10.refresh_from_db()
        assert variant_s10.stock == 6
        assert movs[0].delta == -2

    def test_stock_insuficiente_lanza_error(self, product_s10, db):
        product_s10.stock = 2
        product_s10.save()
        with pytest.raises(InsufficientStockError):
            InventoryService.decrement(
                [{'product': product_s10, 'variant': None, 'quantity': 5}]
            )
        product_s10.refresh_from_db()
        assert product_s10.stock == 2  # rollback

    def test_decremento_crea_alerta_bajo_umbral(self, product_s10, db):
        SiteSettings.objects.update_or_create(pk=1, defaults={'min_stock_threshold': 5})
        product_s10.stock = 6
        product_s10.save()
        InventoryService.decrement(
            [{'product': product_s10, 'variant': None, 'quantity': 2}]
        )
        assert StockAlert.objects.filter(product=product_s10, resolved=False).exists()

    def test_deduplicacion_24h_no_crea_segunda_alerta(self, product_s10, db):
        SiteSettings.objects.update_or_create(pk=1, defaults={'min_stock_threshold': 5})
        product_s10.stock = 4
        product_s10.save()
        InventoryService.decrement(
            [{'product': product_s10, 'variant': None, 'quantity': 0}]
        )
        # Segunda operación dentro de 24h — no debe crear segunda alerta
        InventoryService.decrement(
            [{'product': product_s10, 'variant': None, 'quantity': 0}]
        )
        assert StockAlert.objects.filter(product=product_s10).count() == 1

    def test_restaurar_stock_idempotente(self, product_s10, db):
        product_s10.stock = 5
        product_s10.save()
        InventoryService.restore(
            [{'product': product_s10, 'variant': None, 'quantity': 3}],
            reference='ORD-001',
        )
        # Segunda restauracion con misma referencia — no duplica
        InventoryService.restore(
            [{'product': product_s10, 'variant': None, 'quantity': 3}],
            reference='ORD-001',
        )
        product_s10.refresh_from_db()
        assert product_s10.stock == 8  # solo +3 una vez


# =============================================================================
# UC-INV-04 — Ajuste manual de stock
# =============================================================================

class TestAjusteManual:

    def test_ajuste_producto_sin_variante(
        self, admin_client, product_s10, db
    ):
        res = admin_client.post(
            f'{INV_URL}{product_s10.pk}/adjust/',
            {'delta': 15, 'reason': 'PHYSICAL_COUNT', 'notes': 'Inventario físico'},
            format='json',
        )
        assert res.status_code == 201
        product_s10.refresh_from_db()
        assert product_s10.stock == 25  # stock inicial 10 + delta 15

    def test_ajuste_variante(
        self, admin_client, product_s10, variant_s10, db
    ):
        res = admin_client.post(
            f'{INV_URL}variants/{variant_s10.pk}/adjust/',
            {'delta': 7, 'reason': 'PHYSICAL_COUNT'},
            format='json',
        )
        assert res.status_code == 201
        variant_s10.refresh_from_db()
        assert variant_s10.stock == 15  # stock inicial 8 + delta 7

    def test_ajuste_stock_negativo_retorna_400(
        self, admin_client, product_s10, db
    ):
        res = admin_client.post(
            f'{INV_URL}{product_s10.pk}/adjust/',
            {'delta': -20, 'reason': 'PHYSICAL_COUNT'},
            format='json',
        )
        assert res.status_code == 400

    def test_alertas_pendientes(self, admin_client, product_s10, db):
        StockAlert.objects.create(product=product_s10, stock_at_alert=3)
        res = admin_client.get(ALERTS_URL)
        assert res.status_code == 200
        assert len(res.json()) >= 1
