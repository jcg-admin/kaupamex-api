"""
Tests — Inventory endpoints matching the UI UC-INV-01..05 contract.

These tests cover the new English-keyed JSON contract requested by the
UI agent for end-to-end integration:

UC-INV-01: GET /api/v1/admin/inventory/ with status=NORMAL|LOW|OUT
           plus summary{normal,low,out} and pagination.
UC-INV-02/03: GET /api/v1/admin/inventory/variants/<id>/movements/.
UC-INV-04: POST /api/v1/admin/inventory/variants/<id>/adjust/
           with {new_quantity, reason, observations} and English response
           keys {previous_stock, new_stock, delta, movement_id, variant_id}.
           422 STOCK_NEGATIVO_NO_PERMITIDO on negative new_quantity.
UC-INV-05: POST /api/v1/admin/inventory/import/ accepting initial_state
           and returning English response keys
           {products_created, products_failed, error_report:[{row,field,reason}],
            download_url}. 422 ENCABEZADO_CSV_INVALIDO when headers wrong.
"""
import csv, io, pytest
from decimal import Decimal

pytestmark = pytest.mark.integration

INV_URL    = '/api/v1/admin/inventory/'
IMPORT_URL = '/api/v1/admin/inventory/import/'


@pytest.fixture
def cat_ui(db):
    from apps.catalogue.models import Category
    return Category.objects.create(
        name='Cat UI', slug='cat-ui', is_active=True,
    )


@pytest.fixture
def product_ui(db, cat_ui):
    from apps.catalogue.models import Product
    return Product.objects.create(
        name='Prod UI', slug='prod-ui', sku='UI-001',
        description='', category=cat_ui,
        price=Decimal('500.00'), stock=10,
        is_active=True, is_published=True,
    )


@pytest.fixture
def variant_ui(db, product_ui):
    from apps.chartsize.models import VariantType, VariantOption, ProductVariant
    vt = VariantType.objects.create(
        product=product_ui, name='Tamano', order=0,
    )
    opt = VariantOption.objects.create(
        variant_type=vt, label='Mediana', slug='mediana-ui', order=0,
    )
    return ProductVariant.objects.create(
        product=product_ui, option=opt,
        sku_suffix='MED', stock=10, is_active=True,
    )


def _make_csv(rows, headers=None):
    headers = headers or ['name', 'sku', 'base_price', 'category_slug']
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=headers)
    w.writeheader()
    for row in rows:
        w.writerow(row)
    buf.seek(0)
    return io.BytesIO(buf.read().encode('utf-8'))


# =============================================================================
# UC-INV-01 — Dashboard with English status filters and summary
# =============================================================================

class TestDashboardSummary:

    def test_response_contains_summary_block(
        self, admin_client, product_ui, variant_ui, db
    ):
        res = admin_client.get(INV_URL)
        assert res.status_code == 200
        data = res.json()
        assert 'summary' in data
        for key in ('normal', 'low', 'out', 'total'):
            assert key in data['summary'], f'Missing summary.{key}'

    def test_summary_counts_match_results(
        self, admin_client, product_ui, variant_ui, db
    ):
        res = admin_client.get(INV_URL)
        data = res.json()
        s = data['summary']
        assert s['total'] == s['normal'] + s['low'] + s['out']

    def test_filter_status_low_english_alias(
        self, admin_client, product_ui, variant_ui, db
    ):
        from apps.settings_app.models import SiteSettings
        SiteSettings.objects.update_or_create(
            pk=1, defaults={'min_stock_threshold': 5},
        )
        variant_ui.stock = 3
        variant_ui.save()
        res = admin_client.get(INV_URL, {'status': 'LOW'})
        assert res.status_code == 200
        statuses = {r['status'] for r in res.json()['results']}
        # Backend may emit BAJO (spanish) or LOW; both are valid aliases.
        assert statuses <= {'BAJO', 'LOW'}

    def test_filter_status_out_english_alias(
        self, admin_client, product_ui, variant_ui, db
    ):
        variant_ui.stock = 0
        variant_ui.save()
        res = admin_client.get(INV_URL, {'status': 'OUT'})
        assert res.status_code == 200
        for r in res.json()['results']:
            assert r['status'] in ('AGOTADO', 'OUT')

    def test_pagination_block_present(
        self, admin_client, product_ui, variant_ui, db
    ):
        res = admin_client.get(INV_URL)
        data = res.json()
        assert 'pagination' in data
        for key in ('page', 'page_size', 'total_pages'):
            assert key in data['pagination']


# =============================================================================
# UC-INV-02 / UC-INV-03 — Movements log for a variant
# =============================================================================

class TestVariantMovementsLog:

    def test_movements_endpoint_returns_200(
        self, admin_client, product_ui, variant_ui, db
    ):
        url = f'{INV_URL}variants/{variant_ui.pk}/movements/'
        res = admin_client.get(url)
        assert res.status_code == 200

    def test_movements_returns_list(
        self, admin_client, product_ui, variant_ui, db
    ):
        from apps.inventory.services import InventoryService
        InventoryService.adjust(
            product=product_ui, variant=variant_ui,
            delta=3, notes='entrada',
        )
        url = f'{INV_URL}variants/{variant_ui.pk}/movements/'
        res = admin_client.get(url)
        data = res.json()
        assert 'results' in data
        assert len(data['results']) >= 1
        m = data['results'][0]
        for key in ('id', 'delta', 'stock_after', 'movement_type', 'created_at'):
            assert key in m

    def test_movements_unauthenticated_returns_401(
        self, api_client, product_ui, variant_ui, db
    ):
        url = f'{INV_URL}variants/{variant_ui.pk}/movements/'
        res = api_client.get(url)
        assert res.status_code == 401

    def test_movements_variant_not_found_returns_404(
        self, admin_client, db
    ):
        url = f'{INV_URL}variants/999999/movements/'
        res = admin_client.get(url)
        assert res.status_code == 404


# =============================================================================
# UC-INV-04 — Manual adjust with new_quantity (UI contract)
# =============================================================================

class TestAdjustNewQuantity:

    def test_adjust_with_new_quantity_returns_english_keys(
        self, admin_client, product_ui, variant_ui, db
    ):
        url = f'{INV_URL}variants/{variant_ui.pk}/adjust/'
        res = admin_client.post(url, {
            'new_quantity': 25,
            'reason': 'CONTEO_FISICO',
            'observations': 'Inventario semestral',
        }, format='json')
        assert res.status_code == 201, res.content
        data = res.json()
        for key in ('variant_id', 'previous_stock', 'new_stock',
                    'delta', 'movement_id'):
            assert key in data, f'missing {key}'
        assert data['previous_stock'] == 10
        assert data['new_stock']      == 25
        assert data['delta']          == 15
        assert data['variant_id']     == variant_ui.pk

    def test_adjust_negative_new_quantity_returns_422(
        self, admin_client, variant_ui, db
    ):
        url = f'{INV_URL}variants/{variant_ui.pk}/adjust/'
        res = admin_client.post(url, {
            'new_quantity': -5,
            'reason': 'MERMA',
        }, format='json')
        assert res.status_code == 422
        assert res.json()['codigo_error'] == 'STOCK_NEGATIVO_NO_PERMITIDO'

    def test_adjust_decreases_stock_correctly(
        self, admin_client, variant_ui, db
    ):
        url = f'{INV_URL}variants/{variant_ui.pk}/adjust/'
        res = admin_client.post(url, {
            'new_quantity': 4,
            'reason': 'MERMA',
            'observations': 'Producto danado',
        }, format='json')
        assert res.status_code == 201
        variant_ui.refresh_from_db()
        assert variant_ui.stock == 4
        assert res.json()['delta'] == -6

    def test_adjust_missing_reason_returns_400(
        self, admin_client, variant_ui, db
    ):
        url = f'{INV_URL}variants/{variant_ui.pk}/adjust/'
        res = admin_client.post(url, {'new_quantity': 5}, format='json')
        assert res.status_code == 400

    def test_adjust_records_stock_movement_with_reason(
        self, admin_client, variant_ui, db
    ):
        from apps.inventory.models import StockMovement
        url = f'{INV_URL}variants/{variant_ui.pk}/adjust/'
        admin_client.post(url, {
            'new_quantity': 20,
            'reason': 'CONTEO_FISICO',
            'observations': 'Auditoria',
        }, format='json')
        mov = StockMovement.objects.filter(
            variant=variant_ui, movement_type='ADJUSTMENT',
        ).latest('created_at')
        # reason is stored in notes (free-text) or in a dedicated field; both ok
        notes = mov.notes
        assert 'CONTEO_FISICO' in notes or 'Auditoria' in notes


# =============================================================================
# UC-INV-05 — CSV import with English response keys + initial_state
# =============================================================================

class TestImportEnglishKeys:

    def test_response_uses_english_keys(
        self, admin_client, cat_ui, db
    ):
        rows = [
            {'name': 'P1', 'sku': 'EN-001',
             'base_price': '100.00', 'category_slug': cat_ui.slug},
        ]
        res = admin_client.post(IMPORT_URL, {
            'file':          _make_csv(rows),
            'initial_state': 'BORRADOR',
        }, format='multipart')
        assert res.status_code == 200, res.content
        data = res.json()
        for key in ('products_created', 'products_failed',
                    'error_report', 'download_url'):
            assert key in data, f'missing {key}'
        assert data['products_created'] == 1
        assert data['products_failed']  == 0

    def test_error_report_uses_row_field_reason_keys(
        self, admin_client, cat_ui, db
    ):
        rows = [
            {'name': 'Bad', 'sku': 'EN-BAD-1',
             'base_price': 'not-a-number', 'category_slug': cat_ui.slug},
        ]
        res = admin_client.post(IMPORT_URL, {
            'file': _make_csv(rows),
        }, format='multipart')
        assert res.status_code == 200
        report = res.json()['error_report']
        assert len(report) >= 1
        for entry in report:
            for key in ('row', 'field', 'reason'):
                assert key in entry, f'missing {key} in error_report entry'

    def test_invalid_headers_returns_422_encabezado_csv_invalido(
        self, admin_client, db,
    ):
        csv_f = _make_csv(
            [{'a': '1', 'b': '2'}],
            headers=['a', 'b'],
        )
        res = admin_client.post(IMPORT_URL, {
            'file': csv_f,
        }, format='multipart')
        assert res.status_code == 422
        assert res.json()['codigo_error'] == 'ENCABEZADO_CSV_INVALIDO'

    def test_initial_state_activo_creates_active_products(
        self, admin_client, cat_ui, db,
    ):
        from apps.catalogue.models import Product
        rows = [
            {'name': 'Activo X', 'sku': 'EN-ACT-1',
             'base_price': '300.00', 'category_slug': cat_ui.slug},
        ]
        res = admin_client.post(IMPORT_URL, {
            'file':          _make_csv(rows),
            'initial_state': 'ACTIVO',
        }, format='multipart')
        assert res.status_code == 200
        p = Product.objects.get(sku='EN-ACT-1')
        assert p.is_active is True

    def test_initial_state_default_is_borrador(
        self, admin_client, cat_ui, db,
    ):
        from apps.catalogue.models import Product
        rows = [
            {'name': 'Borrador D', 'sku': 'EN-BOR-1',
             'base_price': '300.00', 'category_slug': cat_ui.slug},
        ]
        admin_client.post(IMPORT_URL, {
            'file': _make_csv(rows),
        }, format='multipart')
        p = Product.objects.get(sku='EN-BOR-1')
        assert p.is_active is False


# =============================================================================
# D-006 — UC-INV-05 Alt C: descarga del CSV con el error_report
# =============================================================================

class TestImportReportDownload:
    """download_url debe apuntar a un CSV descargable con los errores."""

    def test_download_url_set_when_there_are_errors(
        self, admin_client, cat_ui, db,
    ):
        # CSV con 1 fila que falla (precio invalido) -> error_report no vacio.
        rows = [
            {'name': 'Bad price', 'sku': 'D006-BAD',
             'base_price': 'NaN', 'category_slug': cat_ui.slug},
        ]
        res = admin_client.post(IMPORT_URL, {
            'file': _make_csv(rows),
        }, format='multipart')
        assert res.status_code == 200
        data = res.json()
        assert data['products_failed'] >= 1
        download_url = data['download_url']
        assert download_url, 'download_url debe estar presente si hubo errores'
        assert 'import-reports/' in download_url
        assert download_url.endswith('.csv')

    def test_download_url_is_null_when_no_errors(
        self, admin_client, cat_ui, db,
    ):
        rows = [
            {'name': 'OK', 'sku': 'D006-OK',
             'base_price': '100.00', 'category_slug': cat_ui.slug},
        ]
        res = admin_client.post(IMPORT_URL, {
            'file': _make_csv(rows),
        }, format='multipart')
        assert res.status_code == 200
        data = res.json()
        assert data['products_failed'] == 0
        assert data['download_url'] is None

    def test_download_endpoint_returns_csv(
        self, admin_client, cat_ui, db,
    ):
        # Provocamos 1 error.
        rows = [
            {'name': 'Sin categoria', 'sku': 'D006-CAT',
             'base_price': '100', 'category_slug': 'no-existe'},
        ]
        res = admin_client.post(IMPORT_URL, {
            'file': _make_csv(rows),
        }, format='multipart')
        assert res.status_code == 200
        download_url = res.json()['download_url']
        # Tomar el path relativo (de la URL absoluta).
        from urllib.parse import urlparse
        path = urlparse(download_url).path

        dl = admin_client.get(path)
        assert dl.status_code == 200
        assert dl['Content-Type'].startswith('text/csv')
        assert dl['Content-Disposition'].startswith('attachment')
        body = dl.content.decode()
        assert body.splitlines()[0] == 'row,field,reason'
        assert 'D006-CAT' not in body  # row tiene line number
        assert 'category_slug' in body

    def test_download_unknown_report_returns_404(self, admin_client, db):
        res = admin_client.get(
            '/api/v1/admin/inventory/import-reports/no-existe.csv'
        )
        assert res.status_code == 404
        assert res.json()['codigo_error'] == 'REPORTE_NO_ENCONTRADO'

    def test_download_requires_auth(self, api_client, db):
        res = api_client.get(
            '/api/v1/admin/inventory/import-reports/whatever.csv'
        )
        assert res.status_code == 401
