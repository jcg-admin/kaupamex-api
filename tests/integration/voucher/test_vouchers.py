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
from django.utils import timezone
from datetime import timedelta
from apps.catalogue.models import Category, Product
from apps.voucher.models import Voucher, VoucherChangeLog
from apps.voucher.serializers import VoucherSerializer

pytestmark = pytest.mark.integration

VOUCHERS_URL = '/api/v1/admin/vouchers/'
CART_URL     = '/api/v1/cart/'
ITEMS_URL    = '/api/v1/cart/items/'
VOUCHER_APPLY_URL = '/api/v1/cart/voucher/'


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
    return Product.objects.create(
        name='Prod S13', slug='prod-s13', sku='S13-001',
        description='', category=cat_s13,
        price=Decimal('1000.00'), stock=10,
        is_active=True, is_published=True,
    )


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
            'code': 'NUEVO50',
            'voucher_type': 'FIXED',
            'discount_value': '50.00',
            'valid_from': _past(days=1).isoformat(),
            'min_order_amount': '0.00',
        }, format='json')
        assert res.status_code == 201
        assert res.json()['code'] == 'NUEVO50'
        assert res.json()['status'] == 'ACTIVE'

    def test_crear_voucher_porcentaje(self, admin_client, db):
        res = admin_client.post(VOUCHERS_URL, {
            'code': 'PCT20', 'voucher_type': 'PERCENTAGE',
            'discount_pct': '20.00',
            'valid_from': _past(days=1).isoformat(),
            'min_order_amount': '0.00',
        }, format='json')
        assert res.status_code == 201

    def test_crear_voucher_free_shipping(self, admin_client, db):
        res = admin_client.post(VOUCHERS_URL, {
            'code': 'ENVIOGRATIS', 'voucher_type': 'FREE_SHIPPING',
            'valid_from': _past(days=1).isoformat(),
            'min_order_amount': '0.00',
        }, format='json')
        assert res.status_code == 201

    def test_codigo_siempre_en_mayusculas(self, admin_client, db):
        res = admin_client.post(VOUCHERS_URL, {
            'code': 'minusculas', 'voucher_type': 'FIXED',
            'discount_value': '10.00',
            'valid_from': _past(days=1).isoformat(),
            'min_order_amount': '0.00',
        }, format='json')
        assert res.json()['code'] == 'MINUSCULAS'

    def test_codigo_duplicado_retorna_400(self, admin_client, voucher_fixed, db):
        res = admin_client.post(VOUCHERS_URL, {
            'code': 'FIXED50', 'voucher_type': 'FIXED',
            'discount_value': '30.00',
            'valid_from': _past(days=1).isoformat(),
            'min_order_amount': '0.00',
        }, format='json')
        assert res.status_code == 400

    def test_fixed_sin_discount_value_retorna_400(self, admin_client, db):
        res = admin_client.post(VOUCHERS_URL, {
            'code': 'MALF', 'voucher_type': 'FIXED',
            'valid_from': _past(days=1).isoformat(),
            'min_order_amount': '0.00',
        }, format='json')
        assert res.status_code == 400

    def test_percentage_sin_discount_pct_retorna_400(self, admin_client, db):
        res = admin_client.post(VOUCHERS_URL, {
            'code': 'MALF2', 'voucher_type': 'PERCENTAGE',
            'valid_from': _past(days=1).isoformat(),
            'min_order_amount': '0.00',
        }, format='json')
        assert res.status_code == 400

    def test_crear_sin_auth_retorna_401(self, api_client, db):
        res = api_client.post(VOUCHERS_URL, {}, format='json')
        assert res.status_code == 401


# =============================================================================
# UC-PRO-02 — Editar Voucher con auditoría
# =============================================================================

class TestEditarVoucher:

    def test_editar_fecha_vigencia(self, admin_client, voucher_fixed, db):
        new_until = _future(days=30).isoformat()
        res = admin_client.patch(
            f'{VOUCHERS_URL}{voucher_fixed.pk}/',
            {'valid_until': new_until}, format='json',
        )
        assert res.status_code == 200

    def test_editar_crea_change_log(self, admin_client, voucher_fixed, db):
        admin_client.patch(
            f'{VOUCHERS_URL}{voucher_fixed.pk}/',
            {'min_order_amount': '100.00'}, format='json',
        )
        assert VoucherChangeLog.objects.filter(voucher=voucher_fixed).exists()

    def test_campo_inmutable_con_usos_retorna_400(self, admin_client, voucher_fixed, db):
        """FR-PRO-02: code y voucher_type son inmutables si hay usos."""
        voucher_fixed.current_uses = 5
        voucher_fixed.save()
        res = admin_client.patch(
            f'{VOUCHERS_URL}{voucher_fixed.pk}/',
            {'code': 'NUEVO_CODIGO'}, format='json',
        )
        assert res.status_code == 400
        assert 'FIELD_IMMUTABLE_WHILE_USED' in str(res.json())

    def test_editar_max_uses_sin_usos_ok(self, admin_client, voucher_fixed, db):
        res = admin_client.patch(
            f'{VOUCHERS_URL}{voucher_fixed.pk}/',
            {'max_uses': 50}, format='json',
        )
        assert res.status_code == 200
        assert res.json()['max_uses'] == 50


# =============================================================================
# UC-PRO-03 — Desactivar Voucher
# =============================================================================

class TestDesactivarVoucher:

    def test_desactivar_soft_delete(self, admin_client, voucher_fixed, db):
        res = admin_client.delete(f'{VOUCHERS_URL}{voucher_fixed.pk}/')
        assert res.status_code == 204
        voucher_fixed.refresh_from_db()
        assert voucher_fixed.is_active is False
        assert voucher_fixed.deactivated_at is not None

    def test_reactivar_voucher(self, admin_client, voucher_fixed, db):
        voucher_fixed.is_active = False
        voucher_fixed.save()
        res = admin_client.post(f'{VOUCHERS_URL}{voucher_fixed.pk}/activate/')
        assert res.status_code == 200
        assert res.json()['is_active'] is True

    # --- POST /deactivate/ — contrato esperado por el UI (UC-PRO-03) ---

    def test_deactivate_action_marca_inactivo(self, admin_client, voucher_fixed, db):
        """UI llama POST /:id/deactivate/ y espera el voucher serializado."""
        res = admin_client.post(f'{VOUCHERS_URL}{voucher_fixed.pk}/deactivate/')
        assert res.status_code == 200
        body = res.json()
        assert body['is_active'] is False
        assert body['status'] == 'INACTIVE'
        voucher_fixed.refresh_from_db()
        assert voucher_fixed.is_active is False
        assert voucher_fixed.deactivated_at is not None
        assert voucher_fixed.deactivated_by is not None

    def test_deactivate_action_voucher_ya_inactivo_retorna_400(self, admin_client, voucher_fixed, db):
        voucher_fixed.is_active = False
        voucher_fixed.save()
        res = admin_client.post(f'{VOUCHERS_URL}{voucher_fixed.pk}/deactivate/')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'VOUCHER_ALREADY_INACTIVE'

    def test_deactivate_action_sin_auth_retorna_401(self, api_client, voucher_fixed, db):
        res = api_client.post(f'{VOUCHERS_URL}{voucher_fixed.pk}/deactivate/')
        assert res.status_code == 401

    def test_deactivate_action_usuario_normal_retorna_403(self, auth_client, voucher_fixed, db):
        res = auth_client.post(f'{VOUCHERS_URL}{voucher_fixed.pk}/deactivate/')
        assert res.status_code in (401, 403)

    def test_status_expirado(self, db, admin_user):
        v = Voucher.objects.create(
            code='EXPIRADO', voucher_type='FIXED',
            discount_value=Decimal('10.00'),
            valid_from=_past(days=10),
            valid_until=_past(days=1),
            is_active=True, created_by=admin_user,
            min_order_amount=Decimal('0.00'),
        )
        data = VoucherSerializer(v).data
        assert data['status'] == 'EXPIRED'


# =============================================================================
# UC-PRO-04 — Reporte de uso
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
        """FR-CART-04.02 Escenario 4: reemplaza voucher A por B."""
        client, _ = cart_con_item
        client.post(VOUCHER_APPLY_URL, {'code': 'FIXED50'}, format='json')
        res = client.post(VOUCHER_APPLY_URL, {'code': 'PCT15'}, format='json')
        assert res.status_code == 200
        # PCT15 tope $100 > FIXED50 $50 en este caso
        assert Decimal(res.json()['totals']['discount']) == Decimal('100.00')


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
        r = admin_client.post('/api/v1/admin/vouchers/', payload, format='json')
        assert r.status_code == 201
        from apps.voucher.models import VoucherChangeLog
        assert VoucherChangeLog.objects.filter(
            voucher__code='LOG-CREATE-001',
            changes__action='created',
        ).exists()


class TestVoucherChangeLogDelete:
    """D-03: VoucherChangeLog emitted on DELETE."""

    def test_delete_voucher_emits_change_log(self, admin_client, db):
        from apps.voucher.models import Voucher, VoucherChangeLog
        v = Voucher.objects.create(
            code='LOG-DEL-001', voucher_type='FIXED',
            discount_value='10.00', valid_from='2020-01-01T00:00:00Z',
        )
        r = admin_client.delete(f'/api/v1/admin/vouchers/{v.id}/')
        assert r.status_code == 204
        assert VoucherChangeLog.objects.filter(
            voucher_id=v.id,
            changes__action='deleted',
        ).exists()


class TestVoucherReportPagination:
    """D-09: Report supports pagination and status filter."""

    def test_report_returns_paginated_structure(self, admin_client, db):
        r = admin_client.get('/api/v1/admin/vouchers/report/')
        assert r.status_code == 200
        data = r.json()
        assert 'count' in data
        assert 'results' in data
        assert 'page' in data
        assert 'pages' in data

    def test_report_filters_by_status(self, admin_client, db):
        from apps.voucher.models import Voucher
        from django.utils import timezone
        Voucher.objects.create(
            code='RPT-ACTIVE-001', voucher_type='FIXED',
            discount_value='10.00',
            valid_from=timezone.now(),
            is_active=True,
        )
        r = admin_client.get('/api/v1/admin/vouchers/report/?status=ACTIVE')
        assert r.status_code == 200
        results = r.json()['results']
        for item in results:
            assert item['status'] == 'ACTIVE'
