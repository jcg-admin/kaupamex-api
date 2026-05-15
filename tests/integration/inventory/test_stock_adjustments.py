"""
Tests — Stock restoration, delta adjustments and CSV import

UC-INV-03: Restore stock (idempotent service)
UC-INV-04: Manual delta adjustment
UC-INV-05: Import products from CSV
"""
import csv, io, pytest
from decimal import Decimal

pytestmark = pytest.mark.integration

INV_URL       = '/api/v1/admin/inventory/'
IMPORT_URL    = '/api/v1/admin/inventory/import/'


@pytest.fixture
def cat_s11(db):
    from apps.catalogue.models import Category
    return Category.objects.create(
        name='Cat S11', slug='cat-s11', is_active=True
    )


@pytest.fixture
def product_s11(db, cat_s11):
    from apps.catalogue.models import Product
    return Product.objects.create(
        name='Prod S11', slug='prod-s11', sku='S11-001',
        description='', category=cat_s11,
        price=Decimal('600.00'), stock=10,
        is_active=True, is_published=True,
    )


@pytest.fixture
def variant_type_s11(db, product_s11):
    from apps.chartsize.models import VariantType
    return VariantType.objects.create(
        product=product_s11, name='Presentacion', order=0
    )


@pytest.fixture
def opt_s11(db, variant_type_s11):
    from apps.chartsize.models import VariantOption
    return VariantOption.objects.create(
        variant_type=variant_type_s11, label='100ml',
        slug='100ml-s11', order=0
    )


@pytest.fixture
def variant_s11(db, product_s11, opt_s11):
    from apps.chartsize.models import ProductVariant
    return ProductVariant.objects.create(
        product=product_s11, option=opt_s11,
        sku_suffix='100', stock=6, is_active=True,
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
# UC-INV-04 — Ajuste por Delta (corrección H-S11-002)
# =============================================================================

class TestAjusteDelta:

    def test_ajuste_positivo_incrementa_stock(
        self, admin_client, product_s11, db
    ):
        """Delta +5 sobre stock=10 → 15."""
        res = admin_client.post(
            f'{INV_URL}{product_s11.pk}/adjust/',
            {'delta': 5, 'notes': 'Recepción proveedor'},
            format='json',
        )
        assert res.status_code == 201
        product_s11.refresh_from_db()
        assert product_s11.stock == 15

    def test_ajuste_negativo_reduce_stock(
        self, admin_client, product_s11, db
    ):
        """Delta -3 sobre stock=10 → 7."""
        res = admin_client.post(
            f'{INV_URL}{product_s11.pk}/adjust/',
            {'delta': -3, 'notes': 'Merma'},
            format='json',
        )
        assert res.status_code == 201
        product_s11.refresh_from_db()
        assert product_s11.stock == 7

    def test_ajuste_que_da_negativo_retorna_400(
        self, admin_client, product_s11, db
    ):
        """Delta -20 sobre stock=10 → -10 → rechazado."""
        res = admin_client.post(
            f'{INV_URL}{product_s11.pk}/adjust/',
            {'delta': -20},
            format='json',
        )
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'STOCK_NEGATIVO'
        product_s11.refresh_from_db()
        assert product_s11.stock == 10  # sin cambio

    def test_ajuste_variante_positivo(
        self, admin_client, product_s11, variant_s11, db
    ):
        """Delta +4 sobre variant.stock=6 → 10."""
        res = admin_client.post(
            f'{INV_URL}variants/{variant_s11.pk}/adjust/',
            {'delta': 4, 'notes': 'Entrada almacen'},
            format='json',
        )
        assert res.status_code == 201
        variant_s11.refresh_from_db()
        assert variant_s11.stock == 10

    def test_ajuste_registra_referencia_admin(
        self, admin_client, admin_user, product_s11, db
    ):
        """FR-INV-04.02: referencia = ADMIN:<pk>."""
        from apps.inventory.models import StockMovement
        admin_client.post(
            f'{INV_URL}{product_s11.pk}/adjust/',
            {'delta': 1, 'notes': 'Test'},
            format='json',
        )
        mov = StockMovement.objects.filter(
            product=product_s11,
            movement_type='ADJUSTMENT'
        ).latest('created_at')
        assert mov.reference.startswith('ADMIN:')
        assert mov.notes == 'Test'

    def test_ajuste_cero_permitido(self, admin_client, product_s11, db):
        """Delta 0 es válido (registra un movimiento sin cambio)."""
        res = admin_client.post(
            f'{INV_URL}{product_s11.pk}/adjust/',
            {'delta': 0},
            format='json',
        )
        assert res.status_code == 201
        product_s11.refresh_from_db()
        assert product_s11.stock == 10


# =============================================================================
# UC-INV-03 — Restaurar stock (idempotencia y correctitud)
# =============================================================================

class TestRestaurarStock:

    def test_restaurar_incrementa_stock(self, product_s11, db):
        from apps.inventory.services import InventoryService
        product_s11.stock = 3
        product_s11.save()
        InventoryService.restore(
            [{'product': product_s11, 'variant': None, 'quantity': 4}],
            reference='ORD-S11-001',
        )
        product_s11.refresh_from_db()
        assert product_s11.stock == 7

    def test_restaurar_idempotente_misma_referencia(self, product_s11, db):
        from apps.inventory.services import InventoryService
        product_s11.stock = 5
        product_s11.save()
        for _ in range(3):
            InventoryService.restore(
                [{'product': product_s11, 'variant': None, 'quantity': 3}],
                reference='ORD-S11-DUP',
            )
        product_s11.refresh_from_db()
        assert product_s11.stock == 8  # solo +3 una vez

    def test_restaurar_sin_referencia_no_es_idempotente(self, product_s11, db):
        """Sin referencia no hay deduplicación — cada llamada restaura."""
        from apps.inventory.services import InventoryService
        product_s11.stock = 0
        product_s11.save()
        InventoryService.restore(
            [{'product': product_s11, 'variant': None, 'quantity': 2}],
            reference='',
        )
        InventoryService.restore(
            [{'product': product_s11, 'variant': None, 'quantity': 2}],
            reference='',
        )
        product_s11.refresh_from_db()
        assert product_s11.stock == 4

    def test_restaurar_variante(self, product_s11, variant_s11, db):
        from apps.inventory.services import InventoryService
        variant_s11.stock = 1
        variant_s11.save()
        InventoryService.restore(
            [{'product': product_s11, 'variant': variant_s11, 'quantity': 5}],
            reference='ORD-VAR-001',
        )
        variant_s11.refresh_from_db()
        assert variant_s11.stock == 6

    def test_check_availability_detecta_insuficiente(
        self, product_s11, db
    ):
        from apps.inventory.services import InventoryService
        product_s11.stock = 2
        product_s11.save()
        result = InventoryService.check_availability(
            [{'product': product_s11, 'variant': None, 'quantity': 5}]
        )
        assert len(result) == 1
        assert result[0]['available'] == 2

    def test_check_availability_stock_suficiente(self, product_s11, db):
        from apps.inventory.services import InventoryService
        product_s11.stock = 10
        product_s11.save()
        result = InventoryService.check_availability(
            [{'product': product_s11, 'variant': None, 'quantity': 5}]
        )
        assert result == []


# =============================================================================
# UC-INV-05 — Importar productos desde CSV
# =============================================================================

class TestImportarProductosCSV:

    def test_import_sin_auth_retorna_401(self, api_client, db):
        csv_f = _make_csv([])
        res = api_client.post(IMPORT_URL, {'file': csv_f}, format='multipart')
        assert res.status_code == 401

    def test_import_csv_valido_crea_productos(
        self, admin_client, cat_s11, db
    ):
        rows = [
            {'name': 'Collar Importado', 'sku': 'IMP-001',
             'base_price': '1200.00', 'category_slug': cat_s11.slug},
            {'name': 'Pulsera Importada', 'sku': 'IMP-002',
             'base_price': '450.00', 'category_slug': cat_s11.slug},
        ]
        res = admin_client.post(IMPORT_URL,
            {'file': _make_csv(rows)}, format='multipart')
        assert res.status_code == 200
        data = res.json()
        assert data['created'] == 2
        assert data['failed'] == 0

    def test_productos_importados_son_borradores(
        self, admin_client, cat_s11, db
    ):
        """FR-INV-05.02: productos creados con is_active=False, is_published=False."""
        from apps.catalogue.models import Product
        rows = [{'name': 'Borrador CSV', 'sku': 'BOR-001',
                 'base_price': '800.00', 'category_slug': cat_s11.slug}]
        admin_client.post(IMPORT_URL, {'file': _make_csv(rows)}, format='multipart')
        p = Product.objects.get(sku='BOR-001')
        assert p.is_active is False
        assert p.is_published is False

    def test_sku_duplicado_va_a_errores(
        self, admin_client, cat_s11, product_s11, db
    ):
        rows = [{'name': 'Dup', 'sku': product_s11.sku,
                 'base_price': '100.00', 'category_slug': cat_s11.slug}]
        res = admin_client.post(IMPORT_URL,
            {'file': _make_csv(rows)}, format='multipart')
        assert res.status_code == 200
        assert res.json()['failed'] == 1
        assert res.json()['created'] == 0

    def test_categoria_inexistente_va_a_errores(self, admin_client, db):
        rows = [{'name': 'Prod X', 'sku': 'PX-001',
                 'base_price': '100.00', 'category_slug': 'no-existe'}]
        res = admin_client.post(IMPORT_URL,
            {'file': _make_csv(rows)}, format='multipart')
        assert res.status_code == 200
        assert res.json()['failed'] == 1

    def test_precio_invalido_va_a_errores(self, admin_client, cat_s11, db):
        rows = [{'name': 'Prod Y', 'sku': 'PY-001',
                 'base_price': 'no-es-numero', 'category_slug': cat_s11.slug}]
        res = admin_client.post(IMPORT_URL,
            {'file': _make_csv(rows)}, format='multipart')
        assert res.status_code == 200
        assert res.json()['failed'] == 1

    def test_encabezado_invalido_retorna_400(self, admin_client, db):
        """FR-INV-05.02 Escenario 2: sin columna 'sku' → ENCABEZADO_INVALIDO."""
        # CSV sin columna 'sku'
        csv_f = _make_csv(
            [{'name': 'X', 'price': '100', 'cat': 'test'}],
            headers=['name', 'price', 'cat']
        )
        res = admin_client.post(IMPORT_URL, {'file': csv_f}, format='multipart')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'ENCABEZADO_INVALIDO'

    def test_filas_validas_e_invalidas_mixtas(
        self, admin_client, cat_s11, db
    ):
        """Filas válidas se crean; inválidas van a errors sin bloquear las demás."""
        rows = [
            {'name': 'OK 1', 'sku': 'MIX-001',
             'base_price': '500.00', 'category_slug': cat_s11.slug},
            {'name': 'Falla', 'sku': 'MIX-002',
             'base_price': 'malo', 'category_slug': cat_s11.slug},
            {'name': 'OK 2', 'sku': 'MIX-003',
             'base_price': '600.00', 'category_slug': cat_s11.slug},
        ]
        res = admin_client.post(IMPORT_URL,
            {'file': _make_csv(rows)}, format='multipart')
        assert res.status_code == 200
        assert res.json()['created'] == 2
        assert res.json()['failed'] == 1

    def test_polling_job_no_encontrado(self, admin_client, db):
        res = admin_client.get(f'{IMPORT_URL}uuid-que-no-existe/')
        assert res.status_code == 404
        assert res.json()['codigo_error'] == 'JOB_NO_ENCONTRADO'

    def test_import_csv_sin_archivo_retorna_400(self, admin_client, db):
        res = admin_client.post(IMPORT_URL, {}, format='multipart')
        assert res.status_code == 400
