"""
Tests — POST /api/v2/payments/mercadopago/ (F6 Tier B, GAP-I1)

Verifica el endpoint canónico gateway-específico para MercadoPago.
El gateway queda implícito en la URL — no se envía `gateway` en el body.

UC-PAY-01: Procesar pago con MercadoPago
"""
import json
import pytest
from addons.sale.models import SaleOrder
from decimal import Decimal
from unittest.mock import patch, MagicMock
from decouple import config
from addons.catalogue.models import Category, Product
from addons.payment.models import PaymentGateway
from addons.payment.models import Payment, PaymentGatewayEvent
from tests.factories.order_factory import make_order
from tests.factories.order_factory import mark_delivered

pytestmark = pytest.mark.integration

MP_URL = '/api/v2/payments/mercadopago/'


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def cat_mp(db):
    return Category.objects.create(name='Cat MP', slug='cat-mp', is_active=True)


@pytest.fixture
def prod_mp(db, cat_mp):
    p = Product.objects.create(
        name='Collar Yoruba', slug='collar-yoruba', sku='MP-001',
        description='',
        price=Decimal('1500.00'), stock=10,
        is_active=True, is_published=True,
    )
    p.categories.add(cat_mp)
    return p


@pytest.fixture
def orden_mp(db, user, prod_mp):
    """Orden PENDING con OrderValue_GONE para tests de MercadoPago."""
    order = make_order(user=user, status='PENDING')
    SaleOrderLine.objects.create(
        order=order, product_name=prod_mp.name,
        sku=prod_mp.sku, unit_price=prod_mp.price,
        quantity=2, subtotal=prod_mp.price * 2,
    )
    OrderValue_GONE.objects.create(
        order=order,
        subtotal=Decimal('3000.00'), tax=Decimal('0.00'),
        shipping_cost=Decimal('0.00'), discount=Decimal('0.00'),
        total=Decimal('3000.00'),
    )
    DeliveryAddress.objects.create(
        order=order, recipient_name='Test User',
        street='Av. Reforma 100', city='CDMX',
        state='Ciudad de Mexico', zip_code='06600',
    )
    return order


@pytest.fixture
def mp_gateway(db, admin_user):
    gw = PaymentGateway(
        name='MercadoPago Test',
        gateway='MERCADOPAGO',
        is_active=True,
    )
    gw.set_credentials({
        'access_token': config('MP_TEST_ACCESS_TOKEN', default='TEST-ACCESS-TOKEN-FAKE'),
        'public_key':   config('MP_TEST_PUBLIC_KEY',   default='TEST-PUBLIC-KEY-FAKE'),
    })
    gw.save()
    return gw


@pytest.fixture
def mock_sdk():
    with patch('addons.payment_mercado_pago.gateway.mercadopago') as mock_mp:
        sdk = MagicMock()
        mock_mp.SDK.return_value = sdk
        sdk.preference.return_value.create.return_value = {
            'status': 201,
            'response': {
                'id': 'PREF-MP-GATEWAY-001',
                'init_point': 'https://www.mercadopago.com.mx/checkout/v1/redirect?pref_id=PREF-MP-GATEWAY-001',
            },
        }
        sdk.payment.return_value.get.return_value = {
            'status': 200,
            'response': {
                'id': 99999, 'status': 'approved',
                'transaction_amount': 3000.00, 'installments': 1,
            },
        }
        yield sdk


# =============================================================================
# Happy path
# =============================================================================

class TestMercadoPagoGatewayURL:

    def test_sin_campo_gateway_retorna_201(self, auth_client, orden_mp, mp_gateway, mock_sdk):
        """Gateway-specific URL: no se necesita el campo `gateway` en el body."""
        res = auth_client.post(MP_URL, {'order_number': orden_mp.order_number}, format='json')
        assert res.status_code == 201
        data = res.json()
        assert 'checkout_url' in data
        assert data['checkout_url'].startswith('https://')
        assert data['order_number'] == orden_mp.order_number
        assert data['installments'] == 1

    def test_crea_payment_mercadopago_en_bd(self, auth_client, orden_mp, mp_gateway, mock_sdk):
        auth_client.post(MP_URL, {'order_number': orden_mp.order_number}, format='json')
        payment = Payment.objects.get(order=orden_mp)
        assert payment.gateway == 'MERCADOPAGO'
        assert payment.status == 'PENDING'
        assert payment.preference_id == 'PREF-MP-GATEWAY-001'

    def test_registra_evento_auditoria(self, auth_client, orden_mp, mp_gateway, mock_sdk):
        auth_client.post(MP_URL, {'order_number': orden_mp.order_number}, format='json')
        payment = Payment.objects.get(order=orden_mp)
        event = PaymentGatewayEvent.objects.filter(
            payment=payment, event_type='PREFERENCE_CREATED',
        ).first()
        assert event is not None
        body = json.loads(event.raw_body)
        assert body['preference_id'] == 'PREF-MP-GATEWAY-001'

    def test_campo_gateway_en_body_es_ignorado(self, auth_client, orden_mp, mp_gateway, mock_sdk):
        """Si alguien pasa gateway=PAYPAL al endpoint de MP, se usa MP de todas formas."""
        res = auth_client.post(
            MP_URL,
            {'order_number': orden_mp.order_number, 'gateway': 'PAYPAL'},
            format='json',
        )
        # El serializer no tiene el campo gateway → se ignora silenciosamente
        assert res.status_code == 201
        payment = Payment.objects.get(order=orden_mp)
        assert payment.gateway == 'MERCADOPAGO'

    def test_con_cuotas_msi(self, auth_client, orden_mp, mp_gateway, mock_sdk):
        res = auth_client.post(
            MP_URL,
            {'order_number': orden_mp.order_number, 'installments': 3},
            format='json',
        )
        assert res.status_code == 201
        assert res.json()['installments'] == 3

    def test_credenciales_no_en_respuesta(self, auth_client, orden_mp, mp_gateway, mock_sdk):
        """BR-009: credenciales del gateway NUNCA en la respuesta."""
        res = auth_client.post(MP_URL, {'order_number': orden_mp.order_number}, format='json')
        body_str = json.dumps(res.json())
        assert 'TEST-ACCESS-TOKEN-FAKE' not in body_str
        assert 'TEST-PUBLIC-KEY-FAKE' not in body_str
        assert 'access_token' not in body_str


# =============================================================================
# Error paths
# =============================================================================

class TestMercadoPagoGatewayURLErrores:

    def test_sin_autenticar_retorna_401(self, api_client, orden_mp, mp_gateway, mock_sdk):
        res = api_client.post(MP_URL, {'order_number': orden_mp.order_number}, format='json')
        assert res.status_code == 401

    def test_orden_ajena_retorna_400(
        self, api_client, django_user_model, orden_mp, mp_gateway, mock_sdk,
    ):
        attacker = django_user_model.objects.create_user(
            email='attacker_mp@test.mx', password='Attack123!',
        )
        api_client.force_authenticate(user=attacker)
        res = api_client.post(MP_URL, {'order_number': orden_mp.order_number}, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'ORDER_NOT_FOUND'

    def test_orden_no_pending_retorna_400(self, auth_client, orden_mp, mp_gateway, mock_sdk):
        # O2C V5d: no-pagable se produce por los ejes (entregada), no
        # escribiendo la columna ('APPROVED' ni era un SaleOrder status valido).
        mark_delivered(orden_mp)
        res = auth_client.post(MP_URL, {'order_number': orden_mp.order_number}, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'ORDER_NOT_PAYABLE'

    def test_amount_mismatch_retorna_422(self, auth_client, orden_mp, mp_gateway, mock_sdk):
        res = auth_client.post(
            MP_URL,
            {'order_number': orden_mp.order_number, 'expected_amount': '9999.00'},
            format='json',
        )
        assert res.status_code == 422
        assert res.json()['codigo_error'] == 'AMOUNT_MISMATCH'

    def test_gateway_down_retorna_503(self, auth_client, orden_mp, mp_gateway):
        with patch('addons.payment_mercado_pago.gateway.mercadopago') as mock_mp:
            sdk = MagicMock()
            mock_mp.SDK.return_value = sdk
            sdk.preference.return_value.create.return_value = {
                'status': 400,
                'response': {'message': 'Invalid access token'},
            }
            res = auth_client.post(MP_URL, {'order_number': orden_mp.order_number}, format='json')
        assert res.status_code == 503
        assert res.json()['codigo_error'] == 'GATEWAY_UNAVAILABLE'
