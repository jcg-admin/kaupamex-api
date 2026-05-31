"""
Tests — Stock restoration, delta adjustments and CSV import

UC-INV-03: Restore stock (idempotent service)
UC-INV-04: Manual delta adjustment
UC-INV-05: Import products from CSV
"""
import csv, io, pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from decimal import Decimal
from apps.catalogue.models import Category, Product
from apps.chartsize.models import VariantType, VariantOption, ProductVariant
from apps.inventory.models import StockMovement
from apps.inventory.services import InventoryService, InsufficientStockError
from apps.orders.models import Order, OrderItem
from apps.users.models import BusinessEvent

pytestmark = pytest.mark.integration

INV_URL          = '/api/v1/admin/inventory/'
IMPORT_URL       = '/api/v1/admin/inventory/import/'
ZERO_CHECK_URL   = '/api/v1/admin/inventory/variants/{pk}/zero-stock-check/'
VARIANT_ADJ_URL  = '/api/v1/admin/inventory/variants/{pk}/adjust/'


@pytest.fixture
def cat_s11(db):
    return Category.objects.create(
        name='Cat S11', slug='cat-s11', is_active=True
    )


@pytest.fixture
def product_s11(db, cat_s11):
    _p = Product.objects.create(
        name='Prod S11', slug='prod-s11', sku='S11-001',
        description='',
        price=Decimal('600.00'), stock=10,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_s11)
    return _p


@pytest.fixture
def variant_type_s11(db, product_s11):
    return VariantType.objects.create(
        product=product_s11, name='Presentacion', order=0
    )


@pytest.fixture
def opt_s11(db, variant_type_s11):
    return VariantOption.objects.create(
        variant_type=variant_type_s11, label='100ml',
        slug='100ml-s11', order=0
    )


@pytest.fixture
def variant_s11(db, product_s11, opt_s11):
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
    return SimpleUploadedFile('test.csv', buf.read().encode('utf-8'), content_type='text/csv')


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
            {'delta': 5, 'reason': 'PHYSICAL_COUNT', 'notes': 'Recepción proveedor'},
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
            {'delta': -3, 'reason': 'LOSS', 'notes': 'Merma'},
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
            {'delta': -20, 'reason': 'PHYSICAL_COUNT'},
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
            {'delta': 4, 'reason': 'PHYSICAL_COUNT', 'notes': 'Entrada almacen'},
            format='json',
        )
        assert res.status_code == 201
        variant_s11.refresh_from_db()
        assert variant_s11.stock == 10

    def test_ajuste_registra_referencia_admin(
        self, admin_client, admin_user, product_s11, db
    ):
        """FR-INV-04.02: referencia = ADMIN:<pk>."""
        admin_client.post(
            f'{INV_URL}{product_s11.pk}/adjust/',
            {'delta': 1, 'reason': 'PHYSICAL_COUNT', 'notes': 'Test'},
            format='json',
        )
        mov = StockMovement.objects.filter(
            product=product_s11,
            movement_type='ADJUSTMENT'
        ).latest('created_at')
        assert mov.reference.startswith('ADMIN:')
        assert mov.notes == 'Test'

    def test_ajuste_cero_rechazado(self, admin_client, product_s11, db):
        """Delta 0 es inválido — H-CICLO62-02: crearía StockMovement sin efecto."""
        res = admin_client.post(
            f'{INV_URL}{product_s11.pk}/adjust/',
            {'delta': 0, 'reason': 'PHYSICAL_COUNT'},
            format='json',
        )
        assert res.status_code == 400
        product_s11.refresh_from_db()
        assert product_s11.stock == 10  # sin cambio


# =============================================================================
# UC-INV-03 — Restaurar stock (idempotencia y correctitud)
# =============================================================================

class TestRestaurarStock:

    def test_restaurar_incrementa_stock(self, product_s11, db):
        product_s11.stock = 3
        product_s11.save()
        InventoryService.restore(
            [{'product': product_s11, 'variant': None, 'quantity': 4}],
            reference='ORD-S11-001',
        )
        product_s11.refresh_from_db()
        assert product_s11.stock == 7

    def test_restaurar_idempotente_misma_referencia(self, product_s11, db):
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
        product_s11.stock = 2
        product_s11.save()
        result = InventoryService.check_availability(
            [{'product': product_s11, 'variant': None, 'quantity': 5}]
        )
        assert len(result) == 1
        assert result[0]['available'] == 2

    def test_check_availability_stock_suficiente(self, product_s11, db):
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

    def test_encabezado_invalido_retorna_422(self, admin_client, db):
        """
        FR-INV-05.02 Escenario 2: sin columna 'sku' → ENCABEZADO_CSV_INVALIDO.

        UC-INV-05 PARTE 7 (UI contract): el código pasa a
        ENCABEZADO_CSV_INVALIDO y el status a 422 (semantic error).
        El código antiguo ENCABEZADO_INVALIDO se conserva como alias por
        compatibilidad — ver _process_import_csv.
        """
        # CSV sin columna 'sku'
        csv_f = _make_csv(
            [{'name': 'X', 'price': '100', 'cat': 'test'}],
            headers=['name', 'price', 'cat']
        )
        res = admin_client.post(IMPORT_URL, {'file': csv_f}, format='multipart')
        assert res.status_code == 422
        # T-111.1 anti-soft-on-tests (canon EN).
        assert res.json()['codigo_error'] == 'CSV_HEADER_INVALID'

    def test_filas_validas_e_invalidas_mixtas(
        self, admin_client, cat_s11, db
    ):
        """H-CICLO72-02: all-or-nothing — si hay filas inválidas, nada se crea."""
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
        assert res.json()['created'] == 0
        assert res.json()['failed'] == 1

    def test_polling_job_no_encontrado(self, admin_client, db):
        res = admin_client.get(f'{IMPORT_URL}uuid-que-no-existe/')
        assert res.status_code == 404
        # T-111.1 anti-soft-on-tests (canon EN).
        assert res.json()['codigo_error'] == 'JOB_NOT_FOUND'

    def test_import_csv_sin_archivo_retorna_400(self, admin_client, db):
        res = admin_client.post(IMPORT_URL, {}, format='multipart')
        assert res.status_code == 400


# =============================================================================
# UC-INV-04 EX-02 — Guardia de stock en InventoryService.decrement()
# =============================================================================

class TestDecrementGuard:
    """
    UC-INV-04 EX-02: InventoryService.decrement() lanza InsufficientStockError
    cuando la cantidad solicitada supera el stock disponible.
    La excepcion lleva .available con el stock real para que la vista
    pueda incluirlo en la respuesta 409.
    """

    def test_decrement_stock_suficiente_reduce_stock(self, product_s11, db):
        """Camino feliz: decrement con stock suficiente funciona."""
        movs = InventoryService.decrement(
            [{'product': product_s11, 'variant': None, 'quantity': 3}],
            reference='TEST-OK',
        )
        product_s11.refresh_from_db()
        assert product_s11.stock == 7
        assert len(movs) == 1
        assert movs[0].delta == -3

    def test_decrement_stock_exacto_reduce_a_cero(self, product_s11, db):
        """stock == quantity: decrement lleva stock a cero, sin excepcion."""
        movs = InventoryService.decrement(
            [{'product': product_s11, 'variant': None, 'quantity': 10}],
            reference='TEST-ZERO',
        )
        product_s11.refresh_from_db()
        assert product_s11.stock == 0
        assert len(movs) == 1

    def test_decrement_stock_cero_lanza_insufficient_stock_error(
        self, product_s11, db
    ):
        """stock=0, quantity=1 → InsufficientStockError con available=0."""
        product_s11.stock = 0
        product_s11.save()
        with pytest.raises(InsufficientStockError) as exc_info:
            InventoryService.decrement(
                [{'product': product_s11, 'variant': None, 'quantity': 1}],
                reference='TEST-ZERO-GUARD',
            )
        assert exc_info.value.available == 0
        # Stock no debe haber cambiado
        product_s11.refresh_from_db()
        assert product_s11.stock == 0

    def test_decrement_cantidad_mayor_que_stock_lanza_error(
        self, product_s11, db
    ):
        """stock=5, quantity=10 → InsufficientStockError con available=5."""
        product_s11.stock = 5
        product_s11.save()
        with pytest.raises(InsufficientStockError) as exc_info:
            InventoryService.decrement(
                [{'product': product_s11, 'variant': None, 'quantity': 10}],
                reference='TEST-INSUF',
            )
        assert exc_info.value.available == 5
        assert exc_info.value.requested == 10
        # Rollback: stock sin cambio
        product_s11.refresh_from_db()
        assert product_s11.stock == 5

    def test_decrement_variante_stock_insuficiente_lanza_error(
        self, product_s11, variant_s11, db
    ):
        """Variante con stock=6, quantity=7 → InsufficientStockError."""
        with pytest.raises(InsufficientStockError) as exc_info:
            InventoryService.decrement(
                [{'product': product_s11, 'variant': variant_s11, 'quantity': 7}],
                reference='TEST-VAR-INSUF',
            )
        assert exc_info.value.available == 6
        variant_s11.refresh_from_db()
        assert variant_s11.stock == 6  # rollback

    def test_decrement_multiples_items_rollback_total(
        self, product_s11, variant_s11, db
    ):
        """
        Si el segundo item falla, el primero tambien hace rollback
        (atomicidad de la transaccion).
        """
        product_s11.stock = 10
        product_s11.save()
        variant_s11.stock = 2
        variant_s11.save()

        with pytest.raises(InsufficientStockError):
            InventoryService.decrement(
                [
                    {'product': product_s11, 'variant': None, 'quantity': 3},
                    {'product': product_s11, 'variant': variant_s11, 'quantity': 5},
                ],
                reference='TEST-ROLLBACK',
            )

        product_s11.refresh_from_db()
        variant_s11.refresh_from_db()
        assert product_s11.stock == 10   # rollback del primer item
        assert variant_s11.stock == 2    # sin cambio


# =============================================================================
# UC-INV-04 EX-02 — Guard two-round para ajuste a cero (ADR-011)
# =============================================================================

class TestZeroStockGuard:
    """
    UC-INV-04 EX-02: two-round guard cuando stock de variante se ajusta a cero.
    Round 1 detecta órdenes PENDING/PROCESSING (Group 1, daño real).
    Round 2 escribe BusinessEvent (AC-06 / RNF-AUDIT-001) cuando new_quantity=0.
    """

    def _make_order_with_item(self, db, variant, order_status, quantity=1):
        order = Order.objects.create(status=order_status)
        OrderItem.objects.create(
            order=order,
            variant=variant,
            product_name='Test',
            sku=variant.product.sku,
            unit_price=Decimal('100.00'),
            quantity=quantity,
            subtotal=Decimal('100.00') * quantity,
        )
        return order

    # --- Round 1 ---

    def test_round1_sin_ordenes_retorna_requires_confirmation_false(
        self, admin_client, variant_s11, db
    ):
        res = admin_client.get(ZERO_CHECK_URL.format(pk=variant_s11.pk))
        assert res.status_code == 200
        data = res.json()
        assert data['active_orders'] == []
        assert data['requires_confirmation'] is False

    def test_round1_orden_pending_retorna_requires_confirmation_true(
        self, admin_client, variant_s11, db
    ):
        self._make_order_with_item(db, variant_s11, Order.STATUS_PENDING, quantity=2)
        res = admin_client.get(ZERO_CHECK_URL.format(pk=variant_s11.pk))
        assert res.status_code == 200
        data = res.json()
        assert len(data['active_orders']) == 1
        assert data['active_orders'][0]['status'] == Order.STATUS_PENDING
        assert data['active_orders'][0]['quantity'] == 2
        assert data['requires_confirmation'] is True

    def test_round1_orden_processing_retorna_requires_confirmation_true(
        self, admin_client, variant_s11, db
    ):
        self._make_order_with_item(db, variant_s11, Order.STATUS_PROCESSING)
        res = admin_client.get(ZERO_CHECK_URL.format(pk=variant_s11.pk))
        assert res.status_code == 200
        data = res.json()
        assert len(data['active_orders']) == 1
        assert data['requires_confirmation'] is True

    def test_round1_ordenes_paid_excluidas_group2(
        self, admin_client, variant_s11, db
    ):
        """PAID ya decrementó stock — no es Group 1, no activa el guard."""
        self._make_order_with_item(db, variant_s11, Order.STATUS_PAID)
        res = admin_client.get(ZERO_CHECK_URL.format(pk=variant_s11.pk))
        assert res.status_code == 200
        data = res.json()
        assert data['active_orders'] == []
        assert data['requires_confirmation'] is False

    def test_round1_ordenes_shipped_excluidas_group2(
        self, admin_client, variant_s11, db
    ):
        """SHIPPED ya decrementó stock — no es Group 1."""
        self._make_order_with_item(db, variant_s11, Order.STATUS_SHIPPED)
        res = admin_client.get(ZERO_CHECK_URL.format(pk=variant_s11.pk))
        assert res.status_code == 200
        data = res.json()
        assert data['active_orders'] == []
        assert data['requires_confirmation'] is False

    def test_round1_variante_no_encontrada_retorna_404(
        self, admin_client, db
    ):
        res = admin_client.get(ZERO_CHECK_URL.format(pk=99999))
        assert res.status_code == 404
        assert res.json()['codigo_error'] == 'VARIANT_NOT_FOUND'

    def test_round1_sin_auth_retorna_401(self, api_client, variant_s11, db):
        res = api_client.get(ZERO_CHECK_URL.format(pk=variant_s11.pk))
        assert res.status_code == 401

    # --- Round 2 ---

    def test_round2_ajuste_a_cero_escribe_business_event(
        self, admin_client, admin_user, variant_s11, db
    ):
        res = admin_client.post(
            VARIANT_ADJ_URL.format(pk=variant_s11.pk),
            {'new_quantity': 0, 'reason': 'PHYSICAL_COUNT'},
            format='json',
        )
        assert res.status_code == 201
        variant_s11.refresh_from_db()
        assert variant_s11.stock == 0
        ev = BusinessEvent.objects.filter(
            action=BusinessEvent.ACTION_STOCK_ADJUSTED_TO_ZERO,
            target_type=BusinessEvent.TARGET_VARIANT,
            target_id=variant_s11.pk,
        ).first()
        assert ev is not None
        assert ev.actor_id == admin_user.pk

    def test_round2_ajuste_no_cero_no_escribe_business_event(
        self, admin_client, variant_s11, db
    ):
        before = BusinessEvent.objects.filter(
            action=BusinessEvent.ACTION_STOCK_ADJUSTED_TO_ZERO
        ).count()
        res = admin_client.post(
            VARIANT_ADJ_URL.format(pk=variant_s11.pk),
            {'new_quantity': 3, 'reason': 'PHYSICAL_COUNT'},
            format='json',
        )
        assert res.status_code == 201
        assert BusinessEvent.objects.filter(
            action=BusinessEvent.ACTION_STOCK_ADJUSTED_TO_ZERO
        ).count() == before

    def test_round2_business_event_contiene_ordenes_en_riesgo(
        self, admin_client, variant_s11, db
    ):
        """extra_json registra las órdenes en riesgo al momento del ajuste (AC-06)."""
        self._make_order_with_item(db, variant_s11, Order.STATUS_PENDING, quantity=3)
        res = admin_client.post(
            VARIANT_ADJ_URL.format(pk=variant_s11.pk),
            {'new_quantity': 0, 'reason': 'LOSS'},
            format='json',
        )
        assert res.status_code == 201
        ev = BusinessEvent.objects.filter(
            action=BusinessEvent.ACTION_STOCK_ADJUSTED_TO_ZERO,
            target_id=variant_s11.pk,
        ).first()
        assert ev is not None
        assert len(ev.extra_json['orders_at_risk']) == 1
        assert ev.extra_json['orders_at_risk'][0]['quantity'] == 3

    def test_round2_happy_path_no_rompe_ajuste_existente(
        self, admin_client, variant_s11, db
    ):
        """El happy path del ajuste (no a cero) sigue funcionando sin cambios."""
        res = admin_client.post(
            VARIANT_ADJ_URL.format(pk=variant_s11.pk),
            {'new_quantity': 10, 'reason': 'PHYSICAL_COUNT'},
            format='json',
        )
        assert res.status_code == 201
        variant_s11.refresh_from_db()
        assert variant_s11.stock == 10
