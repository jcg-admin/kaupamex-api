"""
Tests — Reembolso de pagos y reintento (UC-PAY-07, UC-PAY-08, UC-PAY-09)

Nombre descriptivo: dominio (reembolso y reintento), no sprint.
"""
import json
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from apps.catalogue.models import Category, Product
from apps.orders.models import Order, OrderItem, OrderValue, OrderAddress
from apps.payments.models import Payment, Refund
from apps.settings_app.models import PaymentGateway
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.integration

REFUND_URL       = lambda o: f'/api/v2/payments/{o}/refund/'
ADMIN_REFUND_URL = lambda pid: f'/api/v2/payments/admin/{pid}/refund/'
INITIATE_URL     = '/api/v1/payments/initiate/'


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cat_ref(db):
    return Category.objects.create(name='Cat Ref', slug='cat-ref', is_active=True)


@pytest.fixture
def prod_ref(db, cat_ref):
    _p = Product.objects.create(
        name='Mano Orula', slug='mano-orula', sku='REF-001',
        description='',
        price=Decimal('3600.00'), stock=5,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_ref)
    return _p


def _make_order_with_payment(user, prod, gateway='MERCADOPAGO', status='APPROVED'):
    """Helper para crear orden + payment en el estado indicado."""

    order = Order.objects.create(user=user, status='PROCESSING' if status == 'APPROVED' else 'PENDING')
    OrderItem.objects.create(
        order=order, product_name=prod.name, sku=prod.sku,
        unit_price=prod.price, quantity=1, subtotal=prod.price,
    )
    OrderValue.objects.create(
        order=order, subtotal=prod.price, tax=(prod.price * Decimal('0.16') / Decimal('1.16')).quantize(Decimal('0.01')),
        shipping_cost=Decimal('0'), discount=Decimal('0'), total=prod.price,
    )
    OrderAddress.objects.create(
        order=order, recipient_name='T', street='S',
        city='CDMX', state='CMX', zip_code='06600',
    )
    payment = Payment.objects.create(
        order=order, gateway=gateway,
        preference_id=f'PREF-REF-{order.pk}',
        gateway_payment_id=f'GW-REF-{order.pk}',
        status=status, amount=prod.price,
    )
    return order, payment


@pytest.fixture
def mp_gateway_ref(db):
    gw = PaymentGateway(name='MP Ref', gateway='MERCADOPAGO', is_active=True)
    gw.set_credentials({'access_token': 'TEST-TOK', 'client_secret': 'TEST-SEC'})
    gw.save()
    return gw


@pytest.fixture
def mock_mp_refund():
    """Mock del SDK de MP para reembolsos."""
    with patch('apps.payments.gateways.mercadopago.mercadopago') as mock_mp:
        sdk = MagicMock()
        mock_mp.SDK.return_value = sdk
        sdk.refund.return_value.create.return_value = {
            'status': 201,
            'response': {
                'id': 999001,
                'payment_id': 12345,
                'amount': 3600.00,
                'status': 'approved',
            },
        }
        yield sdk


@pytest.fixture
def mock_mp_sdk_full():
    """Mock completo del SDK de MP (preference + payment + refund)."""
    with patch('apps.payments.gateways.mercadopago.mercadopago') as mock_mp:
        sdk = MagicMock()
        mock_mp.SDK.return_value = sdk
        sdk.preference.return_value.create.return_value = {
            'status': 201,
            'response': {
                'id': 'PREF-RETRY-001',
                'init_point': 'https://www.mercadopago.com.mx/checkout/v1/redirect?pref_id=PREF-RETRY-001',
            },
        }
        sdk.refund.return_value.create.return_value = {
            'status': 201,
            'response': {'id': 888001, 'amount': 3600.00, 'status': 'approved'},
        }
        yield sdk


# =============================================================================
# UC-PAY-07 — Reembolso (comprador)
# =============================================================================

class TestReembolsoComprador:

    def test_reembolso_total_exitoso(
        self, auth_client, user, prod_ref, mp_gateway_ref, mock_mp_refund, db
    ):
        """FR-PAY-07.02: reembolso total → Payment=REFUNDED, Refund creado."""
        order, payment = _make_order_with_payment(user, prod_ref)

        res = auth_client.post(REFUND_URL(order.order_number), {}, format='json')
        assert res.status_code == 201, res.json()
        data = res.json()
        assert data['status'] == 'APPROVED'   # H-REF-007: no 'PROCESSED'
        assert Decimal(data['amount']) == prod_ref.price

        payment.refresh_from_db()
        assert payment.status == 'REFUNDED'

    def test_reembolso_parcial_actualiza_estado_correctly(
        self, auth_client, user, prod_ref, mp_gateway_ref, db
    ):
        """Reembolso parcial → Payment=PARTIALLY_REFUNDED."""
        order, payment = _make_order_with_payment(user, prod_ref)

        monto_parcial = Decimal('1200.00')
        with patch('apps.payments.gateways.mercadopago.mercadopago') as mock_mp:
            sdk = MagicMock()
            mock_mp.SDK.return_value = sdk
            sdk.refund.return_value.create.return_value = {
                'status': 201,
                'response': {'id': 999002, 'amount': float(monto_parcial), 'status': 'approved'},
            }
            res = auth_client.post(
                REFUND_URL(order.order_number),
                {'amount': str(monto_parcial)},
                format='json',
            )

        assert res.status_code == 201
        payment.refresh_from_db()
        assert payment.status == 'PARTIALLY_REFUNDED'
        assert Decimal(res.json()['amount']) == monto_parcial

    def test_pago_no_aprobado_no_es_reembolsable(
        self, auth_client, user, prod_ref, mp_gateway_ref, db
    ):
        """FR-PAY-07.02: solo pagos APPROVED son reembolsables."""
        order, _ = _make_order_with_payment(
            user, prod_ref, status='FAILED'
        )
        res = auth_client.post(REFUND_URL(order.order_number), {}, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'PAYMENT_NOT_REFUNDABLE'

    def test_rnf_sec_003_orden_ajena_retorna_404(
        self, auth_client, prod_ref, db
    ):
        """RNF-SEC-003: orden de otro usuario → 404, nunca 403."""
        User = get_user_model()
        other = User.objects.create_user(
            username='other_ref', email='other_r@test.com', password='pass'
        )
        order, _ = _make_order_with_payment(other, prod_ref)
        res = auth_client.post(REFUND_URL(order.order_number), {}, format='json')
        assert res.status_code == 404
        assert res.json()['codigo_error'] == 'ORDER_NOT_FOUND'

    def test_gateway_falla_retorna_503(
        self, auth_client, user, prod_ref, mp_gateway_ref, db
    ):
        """FR-PAY-07.02 Escenario 2: gateway no disponible → 503."""
        order, _ = _make_order_with_payment(user, prod_ref)
        with patch('apps.payments.gateways.mercadopago.mercadopago') as mock_mp:
            sdk = MagicMock()
            mock_mp.SDK.return_value = sdk
            sdk.refund.return_value.create.return_value = {
                'status': 400,
                'response': {'message': 'Gateway error'},
            }
            res = auth_client.post(REFUND_URL(order.order_number), {}, format='json')
        assert res.status_code == 503

    def test_reembolso_registra_gateway_refund_id(
        self, auth_client, user, prod_ref, mp_gateway_ref, mock_mp_refund, db
    ):
        """El Refund.gateway_refund_id se guarda para trazabilidad."""
        order, _ = _make_order_with_payment(user, prod_ref)
        auth_client.post(REFUND_URL(order.order_number), {}, format='json')
        refund = Refund.objects.filter(payment__order=order).first()
        assert refund is not None
        assert refund.gateway_refund_id == '999001'


# =============================================================================
# UC-PAY-09 — Reembolso manual (Admin)
# =============================================================================

class TestReembolsoAdmin:

    def test_admin_puede_reembolsar_cualquier_pago(
        self, admin_client, user, prod_ref, mp_gateway_ref, mock_mp_refund, db
    ):
        """UC-PAY-09: admin reembolsa sin restricción de propietario."""
        _, payment = _make_order_with_payment(user, prod_ref)
        res = admin_client.post(
            ADMIN_REFUND_URL(payment.pk),
            {'reason': 'Devolución manual por admin'},
            format='json',
        )
        assert res.status_code == 201, res.json()
        assert res.json()['status'] == 'APPROVED'

    def test_usuario_normal_no_puede_usar_endpoint_admin(
        self, auth_client, user, prod_ref, db
    ):
        """UC-PAY-09: solo admins pueden usar /admin/payments/."""
        _, payment = _make_order_with_payment(user, prod_ref)
        res = auth_client.post(ADMIN_REFUND_URL(payment.pk), {}, format='json')
        assert res.status_code == 403

    def test_admin_reembolso_con_motivo_guardado(
        self, admin_client, user, prod_ref, mp_gateway_ref, mock_mp_refund, db
    ):
        _, payment = _make_order_with_payment(user, prod_ref)
        motivo = 'Fallo en la entrega reportado por logística'
        admin_client.post(
            ADMIN_REFUND_URL(payment.pk),
            {'reason': motivo},
            format='json',
        )
        refund = Refund.objects.filter(payment=payment).first()
        assert refund.reason == motivo

    def test_admin_reembolso_pago_no_aprobado_retorna_400(
        self, admin_client, user, prod_ref, mp_gateway_ref, db
    ):
        _, payment = _make_order_with_payment(user, prod_ref, status='FAILED')
        res = admin_client.post(ADMIN_REFUND_URL(payment.pk), {}, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'PAYMENT_NOT_REFUNDABLE'


# =============================================================================
# UC-PAY-08 — Reintento de pago (reutiliza initiate)
# =============================================================================

class TestReintentoPago:

    def test_reintento_crea_nuevo_payment_conservando_historial(
        self, auth_client, user, prod_ref, mp_gateway_ref, mock_mp_sdk_full, db
    ):
        """FR-PAY-08.01: el pago fallido queda en historial, se crea uno nuevo."""
        order, failed_payment = _make_order_with_payment(
            user, prod_ref, status='FAILED'
        )
        # La orden debe estar en PENDING para reintentar
        order.status = 'PENDING'
        order.save()

        res = auth_client.post(INITIATE_URL, {
            'order_number': order.order_number,
            'gateway':      'MERCADOPAGO',
        }, format='json')

        assert res.status_code == 201, res.json()
        total_payments = Payment.objects.filter(order=order).count()
        assert total_payments == 2  # el FAILED + el nuevo PENDING

        failed_payment.refresh_from_db()
        assert failed_payment.status == 'FAILED'  # el anterior no cambió

    def test_reintento_puede_cambiar_de_gateway(
        self, auth_client, user, prod_ref, mp_gateway_ref, db
    ):
        """FR-PAY-08.01: el comprador puede cambiar al otro gateway."""

        pp_gw = PaymentGateway(name='PP', gateway='PAYPAL', is_active=True)
        pp_gw.set_credentials({
            'client_id': 'PP-TEST', 'client_secret': 'PP-SEC',
            'env': 'sandbox', 'webhook_id': 'WH-TEST',
        })
        pp_gw.save()

        order, _ = _make_order_with_payment(user, prod_ref, status='FAILED')
        order.status = 'PENDING'
        order.save()

        pp_order_resp = MagicMock()
        pp_order_resp.status_code = 201
        pp_order_resp.json.return_value = {
            'id': 'PP-RETRY-001', 'status': 'CREATED',
            'links': [{'rel': 'approve', 'href': 'https://www.sandbox.paypal.com/checkoutnow?token=PP-RETRY-001'}],
        }
        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.json.return_value = {'access_token': 'PP-TOKEN'}

        with patch('apps.payments.gateways.paypal.requests') as mock_req:
            mock_req.post.side_effect = [token_resp, pp_order_resp]
            res = auth_client.post(INITIATE_URL, {
                'order_number': order.order_number,
                'gateway':      'PAYPAL',
            }, format='json')

        assert res.status_code == 201
        payments = Payment.objects.filter(order=order).order_by('-created_at')
        assert payments[0].gateway == 'PAYPAL'
        assert payments[1].gateway == 'MERCADOPAGO'
