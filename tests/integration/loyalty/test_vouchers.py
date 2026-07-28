"""
Tests — Voucher management and cart discount application

UC-PRO-01: Create voucher
UC-PRO-02: Edit voucher with audit log
UC-PRO-03: Deactivate voucher
UC-PRO-04: Usage report
UC-CART-04: Apply discount coupon to cart
"""
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
from addons.catalogue.models import Category, Product
from addons.orders.models import Order, OrderValue
from addons.loyalty.models import Voucher, VoucherChangeLog
from addons.loyalty.serializers import VoucherSerializer
from tests.factories.order_factory import make_order
from addons.orders.status_projection import STATUS_DELIVERED

pytestmark = pytest.mark.integration

VOUCHERS_URL = '/api/v2/admin/vouchers/'
CART_URL     = '/api/v2/cart/'
ITEMS_URL    = '/api/v2/cart/items/'
VOUCHER_APPLY_URL = '/api/v2/cart/voucher/'


def _now():
    return timezone.now()

def _past(**kw):
    return _now() - timedelta(**kw)

def _future(**kw):
    return _now() + timedelta(**kw)


@pytest.fixture
def cat_s13(db):
    return Category.objects.create(name='Cat S13', slug='cat-s13', is_active=True)


@pytest.fixture
def product_s13(db, cat_s13):
    _p = Product.objects.create(
        name='Prod S13', slug='prod-s13', sku='S13-001',
        description='',
        price=Decimal('1000.00'), stock=10,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_s13)
    return _p


@pytest.fixture
def voucher_fixed(db, admin_user):
    return Voucher.objects.create(
        code='FIXED50', voucher_type='FIXED',
        discount_value=Decimal('50.00'),
        min_order_amount=Decimal('0.00'),
        valid_from=_past(days=1),
        is_active=True, created_by=admin_user,
    )


@pytest.fixture
def voucher_pct(db, admin_user):
    return Voucher.objects.create(
        code='PCT15', voucher_type='PERCENTAGE',
        discount_pct=Decimal('15.00'),
        max_discount=Decimal('100.00'),
        min_order_amount=Decimal('0.00'),
        valid_from=_past(days=1),
        is_active=True, created_by=admin_user,
    )


@pytest.fixture
def voucher_fs(db, admin_user):
    return Voucher.objects.create(
        code='FREESHIP', voucher_type='FREE_SHIPPING',
        min_order_amount=Decimal('0.00'),
        valid_from=_past(days=1),
        is_active=True, created_by=admin_user,
    )


@pytest.fixture
def cart_con_item(api_client, product_s13):
    """Carrito anónimo con 1 item de $1000."""
    res = api_client.post(ITEMS_URL, {
        'product_id': product_s13.pk, 'quantity': 1,
    }, format='json')
    token = res['X-Cart-Token']
    api_client.credentials(HTTP_X_CART_TOKEN=token)
    return api_client, token


# =============================================================================
# UC-PRO-01 — Crear Voucher
# =============================================================================

class TestCrearVoucher:

    def test_crear_voucher_fixed(self, admin_client, db):
        res = admin_client.post(VOUCHERS_URL, {
            'code': 'NUEVO50', 'voucher_type': 'FIXED',
            'discount_value': '50.00',
            'valid_from': '2020-01-01T00:00:00Z',
        }, format='json')
        assert res.status_code == 201
        assert res.json()['code'] == 'NUEVO50'

    def test_crear_voucher_porcentaje(self, admin_client, db):
        res = admin_client.post(VOUCHERS_URL, {
            'code': 'PCT10', 'voucher_type': 'PERCENTAGE',
            'discount_pct': '10.00',
            'valid_from': '2020-01-01T00:00:00Z',
        }, format='json')
        assert res.status_code == 201

    def test_crear_voucher_free_shipping(self, admin_client, db):
        res = admin_client.post(VOUCHERS_URL, {
            'code': 'FSHIP', 'voucher_type': 'FREE_SHIPPING',
            'valid_from': '2020-01-01T00:00:00Z',
        }, format='json')
        assert res.status_code == 201

    def test_codigo_siempre_en_mayusculas(self, admin_client, db):
        res = admin_client.post(VOUCHERS_URL, {
            'code': 'minuscula', 'voucher_type': 'FREE_SHIPPING',
            'valid_from': '2020-01-01T00:00:00Z',
        }, format='json')
        assert res.status_code == 201
        assert res.json()['code'] == 'MINUSCULA'

    def test_codigo_duplicado_retorna_400(self, admin_client, voucher_fixed, db):
        res = admin_client.post(VOUCHERS_URL, {
            'code': 'FIXED50', 'voucher_type': 'FIXED',
            'discount_value': '10.00',
            'valid_from': '2020-01-01T00:00:00Z',
        }, format='json')
        assert res.status_code == 400

    def test_fixed_sin_discount_value_retorna_400(self, admin_client, db):
        res = admin_client.post(VOUCHERS_URL, {
            'code': 'NOVAL', 'voucher_type': 'FIXED',
            'valid_from': '2020-01-01T00:00:00Z',
        }, format='json')
        assert res.status_code == 400

    def test_percentage_sin_discount_pct_retorna_400(self, admin_client, db):
        res = admin_client.post(VOUCHERS_URL, {
            'code': 'NOPCT', 'voucher_type': 'PERCENTAGE',
            'valid_from': '2020-01-01T00:00:00Z',
        }, format='json')
        assert res.status_code == 400

    def test_crear_sin_auth_retorna_401(self, api_client, db):
        res = api_client.post(VOUCHERS_URL, {
            'code': 'NOAUTH', 'voucher_type': 'FREE_SHIPPING',
            'valid_from': '2020-01-01T00:00:00Z',
        }, format='json')
        assert res.status_code == 401


# =============================================================================
# UC-PRO-02 — Editar Voucher
# =============================================================================

class TestEditarVoucher:

    def test_editar_fecha_vigencia(self, admin_client, voucher_fixed, db):
        res = admin_client.patch(
            f'{VOUCHERS_URL}{voucher_fixed.pk}/',
            {'valid_until': '2030-12-31T00:00:00Z'},
            format='json',
        )
        assert res.status_code == 200
        assert '2030' in res.json()['valid_until']

    def test_editar_crea_change_log(self, admin_client, voucher_fixed, db):
        admin_client.patch(
            f'{VOUCHERS_URL}{voucher_fixed.pk}/',
            {'valid_until': '2030-12-31T00:00:00Z'},
            format='json',
        )
        assert VoucherChangeLog.objects.filter(
            voucher=voucher_fixed,
            changes__valid_until__isnull=False,
        ).exists()

    def test_campo_inmutable_con_usos_retorna_400(self, admin_client, voucher_fixed, db):
        voucher_fixed.current_uses = 1
        voucher_fixed.save()
        res = admin_client.patch(
            f'{VOUCHERS_URL}{voucher_fixed.pk}/',
            {'code': 'CAMBIADO'},
            format='json',
        )
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'FIELD_IMMUTABLE_WHILE_USED'

    def test_editar_max_uses_sin_usos_ok(self, admin_client, voucher_fixed, db):
        res = admin_client.patch(
            f'{VOUCHERS_URL}{voucher_fixed.pk}/',
            {'max_uses': 100},
            format='json',
        )
        assert res.status_code == 200
        assert res.json()['max_uses'] == 100


# =============================================================================
# UC-PRO-03 — Desactivar Voucher
# =============================================================================

class TestDesactivarVoucher:

    def test_desactivar_soft_delete(self, admin_client, voucher_fixed, db):
        res = admin_client.delete(f'{VOUCHERS_URL}{voucher_fixed.pk}/')
        assert res.status_code == 204
        voucher_fixed.refresh_from_db()
        assert voucher_fixed.is_deleted is True

    def test_reactivar_voucher(self, admin_client, voucher_fixed, db):
        admin_client.delete(f'{VOUCHERS_URL}{voucher_fixed.pk}/')
        res = admin_client.post(f'{VOUCHERS_URL}{voucher_fixed.pk}/activate/')
        assert res.status_code == 200
        assert res.json()['is_active'] is True

    def test_deactivate_action_marca_inactivo(self, admin_client, voucher_fixed, db):
        res = admin_client.post(
            f'{VOUCHERS_URL}{voucher_fixed.pk}/deactivate/',
        )
        assert res.status_code == 200
        assert res.json()['is_active'] is False
        voucher_fixed.refresh_from_db()
        assert voucher_fixed.is_active is False
        assert voucher_fixed.is_deleted is False

    def test_deactivate_action_voucher_ya_inactivo_retorna_400(self, admin_client, voucher_fixed, db):
        admin_client.post(f'{VOUCHERS_URL}{voucher_fixed.pk}/deactivate/')
        res = admin_client.post(f'{VOUCHERS_URL}{voucher_fixed.pk}/deactivate/')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'VOUCHER_ALREADY_INACTIVE'

    def test_deactivate_action_sin_auth_retorna_401(self, api_client, voucher_fixed, db):
        res = api_client.post(f'{VOUCHERS_URL}{voucher_fixed.pk}/deactivate/')
        assert res.status_code == 401

    def test_deactivate_action_usuario_normal_retorna_403(self, auth_client, voucher_fixed, db):
        res = auth_client.post(f'{VOUCHERS_URL}{voucher_fixed.pk}/deactivate/')
        assert res.status_code == 403

    def test_status_expirado(self, db, admin_user):
        v = Voucher.objects.create(
            code='EXPIRED01', voucher_type='FIXED',
            discount_value=Decimal('10'),
            valid_from=_past(days=10),
            valid_until=_past(days=1),
            is_active=True, min_order_amount=Decimal('0'),
            created_by=admin_user,
        )
        s = VoucherSerializer(v)
        assert s.data['status'] == 'EXPIRED'


# =============================================================================
# UC-PRO-04 — Reporte de Uso
# =============================================================================

class TestReporteVouchers:

    def test_reporte_retorna_200(self, admin_client, voucher_fixed, db):
        res = admin_client.get(f'{VOUCHERS_URL}report/')
        assert res.status_code == 200
        assert 'count' in res.json()
        assert 'results' in res.json()

    def test_reporte_incluye_voucher(self, admin_client, voucher_fixed, db):
        res = admin_client.get(f'{VOUCHERS_URL}report/')
        codes = [v['code'] for v in res.json()['results']]
        assert 'FIXED50' in codes

    def test_reporte_roi_nulo_sin_ordenes(self, admin_client, voucher_fixed, db):
        res = admin_client.get(f'{VOUCHERS_URL}report/')
        assert res.status_code == 200
        voucher_data = next(
            v for v in res.json()['results'] if v['code'] == 'FIXED50'
        )
        assert voucher_data['orders_count'] == 0
        assert voucher_data['total_discount_given'] is None
        assert voucher_data['total_revenue_with_voucher'] is None
        assert voucher_data['roi'] is None

    def test_reporte_roi_incluye_aggregates_cuando_hay_ordenes(
        self, admin_client, voucher_fixed, db, admin_user
    ):
        User = get_user_model()
        buyer = User.objects.create_user(
            password='pass',
            email='buyer_roi@test.com',
        )
        order = make_order(
            user=buyer,
            voucher_code=voucher_fixed.code,
            voucher_discount=Decimal('50.00'),
            status=STATUS_DELIVERED,
        )
        OrderValue.objects.create(
            order=order,
            subtotal=Decimal('1000.00'),
            tax=Decimal('0.00'),
            shipping_cost=Decimal('0.00'),
            discount=Decimal('50.00'),
            total=Decimal('950.00'),
        )
        res = admin_client.get(f'{VOUCHERS_URL}report/')
        assert res.status_code == 200
        voucher_data = next(
            v for v in res.json()['results'] if v['code'] == 'FIXED50'
        )
        assert voucher_data['orders_count'] == 1
        assert Decimal(voucher_data['total_discount_given']) == Decimal('50.00')
        assert Decimal(voucher_data['total_revenue_with_voucher']) == Decimal('950.00')
        assert voucher_data['roi'] == round(950.0 / 50.0, 2)

    def test_reporte_filtro_date_from(
        self, admin_client, voucher_fixed, db, admin_user
    ):
        User = get_user_model()
        buyer = User.objects.create_user(
            password='pass',
            email='buyer_datefrom@test.com',
        )
        order = make_order(
            user=buyer,
            voucher_code=voucher_fixed.code,
            voucher_discount=Decimal('50.00'),
            status=STATUS_DELIVERED,
        )
        OrderValue.objects.create(
            order=order,
            subtotal=Decimal('1000.00'),
            tax=Decimal('0.00'),
            shipping_cost=Decimal('0.00'),
            discount=Decimal('50.00'),
            total=Decimal('950.00'),
        )
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        res = admin_client.get(f'{VOUCHERS_URL}report/?date_from={tomorrow}')
        assert res.status_code == 200
        voucher_data = next(
            (v for v in res.json()['results'] if v['code'] == 'FIXED50'), None
        )
        assert voucher_data is not None
        assert voucher_data['orders_count'] == 0

    def test_reporte_csv_export(self, admin_client, voucher_fixed, db):
        res = admin_client.get(f'{VOUCHERS_URL}report/?export=csv')
        assert res.status_code == 200
        assert 'text/csv' in res['Content-Type']
        content = res.content.decode()
        assert 'code' in content
        assert 'FIXED50' in content


# =============================================================================
# UC-CART-04 — Aplicar cupón de descuento
# =============================================================================

class TestAplicarCupon:

    def test_aplicar_voucher_fixed(self, cart_con_item, voucher_fixed, db):
        """FR-CART-04.02 Escenario 1: FIXED $50 sobre subtotal $1000 → descuento $50."""
        client, _ = cart_con_item
        res = client.post(VOUCHER_APPLY_URL, {'code': 'FIXED50'}, format='json')
        assert res.status_code == 200
        totals = res.json()['totals']
        assert Decimal(totals['discount']) == Decimal('50.00')
        assert Decimal(totals['subtotal_net']) == Decimal('950.00')

    def test_aplicar_voucher_percentage(self, cart_con_item, voucher_pct, db):
        """FR-CART-04.02 Escenario 2: 15% de $1000 = $150, pero tope $100."""
        client, _ = cart_con_item
        res = client.post(VOUCHER_APPLY_URL, {'code': 'PCT15'}, format='json')
        assert res.status_code == 200
        totals = res.json()['totals']
        assert Decimal(totals['discount']) == Decimal('100.00')

    def test_aplicar_voucher_free_shipping(self, cart_con_item, voucher_fs, db):
        """FR-CART-04.02 Escenario 3: FREE_SHIPPING — sin descuento en subtotal."""
        client, _ = cart_con_item
        res = client.post(VOUCHER_APPLY_URL, {'code': 'FREESHIP'}, format='json')
        assert res.status_code == 200
        totals = res.json()['totals']
        assert Decimal(totals['discount']) == Decimal('0.00')
        assert res.json()['totals']['free_shipping_applied'] is True

    def test_voucher_no_encontrado_retorna_400(self, cart_con_item, db):
        client, _ = cart_con_item
        res = client.post(VOUCHER_APPLY_URL, {'code': 'NOEXISTE'}, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'VOUCHER_NOT_FOUND'

    def test_voucher_expirado_retorna_400(self, cart_con_item, db, admin_user):
        Voucher.objects.create(
            code='VENCIDO', voucher_type='FIXED', discount_value=Decimal('10'),
            valid_from=_past(days=10), valid_until=_past(days=1),
            is_active=True, min_order_amount=Decimal('0'), created_by=admin_user,
        )
        client, _ = cart_con_item
        res = client.post(VOUCHER_APPLY_URL, {'code': 'VENCIDO'}, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'VOUCHER_EXPIRED'

    def test_voucher_agotado_retorna_400(self, cart_con_item, db, admin_user):
        Voucher.objects.create(
            code='AGOTADO', voucher_type='FIXED', discount_value=Decimal('10'),
            valid_from=_past(days=1), max_uses=5, current_uses=5,
            is_active=True, min_order_amount=Decimal('0'), created_by=admin_user,
        )
        client, _ = cart_con_item
        res = client.post(VOUCHER_APPLY_URL, {'code': 'AGOTADO'}, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'VOUCHER_EXHAUSTED'

    def test_monto_minimo_no_alcanzado_retorna_400(self, cart_con_item, db, admin_user):
        Voucher.objects.create(
            code='MINIMO2000', voucher_type='FIXED', discount_value=Decimal('50'),
            valid_from=_past(days=1), min_order_amount=Decimal('2000'),
            is_active=True, created_by=admin_user,
        )
        client, _ = cart_con_item  # subtotal $1000 < $2000
        res = client.post(VOUCHER_APPLY_URL, {'code': 'MINIMO2000'}, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'MINIMUM_AMOUNT_NOT_REACHED'

    def test_quitar_cupon(self, cart_con_item, voucher_fixed, db):
        client, _ = cart_con_item
        client.post(VOUCHER_APPLY_URL, {'code': 'FIXED50'}, format='json')
        res = client.delete(VOUCHER_APPLY_URL)
        assert res.status_code == 200
        assert Decimal(res.json()['totals']['discount']) == Decimal('0.00')

    def test_quitar_cupon_sin_cupon_retorna_400(self, cart_con_item, db):
        client, _ = cart_con_item
        res = client.delete(VOUCHER_APPLY_URL)
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'NO_ACTIVE_VOUCHER'

    def test_reemplazar_voucher_existente(self, cart_con_item, voucher_fixed, voucher_pct, db):
        """DEC-BC-20: aplicar un segundo voucher cuando ya hay uno activo retorna 409.
        El flujo correcto es DELETE + POST (remover primero, luego aplicar el nuevo)."""
        client, _ = cart_con_item
        client.post(VOUCHER_APPLY_URL, {'code': 'FIXED50'}, format='json')
        # Second apply rejected — must remove first
        res = client.post(VOUCHER_APPLY_URL, {'code': 'PCT15'}, format='json')
        assert res.status_code == 409
        assert res.json()['codigo_error'] == 'VOUCHER_ALREADY_APPLIED'
        # Remove FIXED50 and apply PCT15 succeeds
        client.delete(VOUCHER_APPLY_URL)
        res2 = client.post(VOUCHER_APPLY_URL, {'code': 'PCT15'}, format='json')
        assert res2.status_code == 200
        assert Decimal(res2.json()['totals']['discount']) == Decimal('100.00')


# =============================================================================
# Modelo Voucher — lógica de negocio
# =============================================================================

class TestVoucherModelo:

    def test_calculate_discount_fixed_no_supera_subtotal(self, db):
        v = Voucher(code='T', voucher_type='FIXED', discount_value=Decimal('200'),
                    valid_from=_past(days=1), is_active=True, current_uses=0,
                    min_order_amount=Decimal('0'))
        assert v.calculate_discount(Decimal('50')) == Decimal('50')  # min(200, 50)

    def test_calculate_discount_pct_con_tope(self, db):
        v = Voucher(code='T', voucher_type='PERCENTAGE', discount_pct=Decimal('15'),
                    max_discount=Decimal('100'), valid_from=_past(days=1),
                    is_active=True, current_uses=0, min_order_amount=Decimal('0'))
        assert v.calculate_discount(Decimal('1000')) == Decimal('100')
        assert v.calculate_discount(Decimal('400')) == Decimal('60.00')

    def test_calculate_discount_free_shipping_es_cero(self, db):
        v = Voucher(code='T', voucher_type='FREE_SHIPPING',
                    valid_from=_past(days=1), is_active=True, current_uses=0,
                    min_order_amount=Decimal('0'))
        assert v.calculate_discount(Decimal('500')) == Decimal('0.00')

    def test_is_valid_voucher_activo(self, voucher_fixed, db):
        assert voucher_fixed.is_valid() is True

    def test_is_valid_voucher_inactivo(self, voucher_fixed, db):
        voucher_fixed.is_active = False
        assert voucher_fixed.is_valid() is False


class TestVoucherChangeLogCreate:
    """D-03: VoucherChangeLog emitted on CREATE."""

    def test_create_voucher_emits_change_log(self, admin_client, db):
        payload = {
            'code': 'LOG-CREATE-001',
            'voucher_type': 'FIXED',
            'discount_value': '50.00',
            'valid_from': '2020-01-01T00:00:00Z',
            'max_uses': 10,
        }
        r = admin_client.post('/api/v2/admin/vouchers/', payload, format='json')
        assert r.status_code == 201
        assert VoucherChangeLog.objects.filter(
            voucher__code='LOG-CREATE-001',
            changes__action='created',
        ).exists()


class TestVoucherChangeLogDelete:
    """D-03: VoucherChangeLog emitted on DELETE."""

    def test_delete_voucher_emits_change_log(self, admin_client, db):
        v = Voucher.objects.create(
            code='LOG-DEL-001', voucher_type='FIXED',
            discount_value='10.00', valid_from='2020-01-01T00:00:00Z',
        )
        r = admin_client.delete(f'/api/v2/admin/vouchers/{v.id}/')
        assert r.status_code == 204
        assert VoucherChangeLog.objects.filter(
            voucher_id=v.id,
            changes__action='deleted',
        ).exists()


class TestVoucherReportPagination:
    """D-09: Report supports pagination and status filter."""

    def test_report_returns_paginated_structure(self, admin_client, db):
        r = admin_client.get('/api/v2/admin/vouchers/report/')
        assert r.status_code == 200
        data = r.json()
        assert 'count' in data
        assert 'results' in data
        assert 'page' in data
        assert 'pages' in data

    def test_report_filters_by_status(self, admin_client, db):
        Voucher.objects.create(
            code='RPT-ACTIVE-001', voucher_type='FIXED',
            discount_value='10.00',
            valid_from=timezone.now(),
            is_active=True,
        )
        r = admin_client.get('/api/v2/admin/vouchers/report/?status=ACTIVE')
        assert r.status_code == 200
        results = r.json()['results']
        for item in results:
            assert item['status'] == 'ACTIVE'
