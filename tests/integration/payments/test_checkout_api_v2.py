"""
Tests — MercadoPago Checkout API v2 (ADR-018)

POST /api/v2/payments/initiate/   CheckoutApiPaymentView
GET  /api/v2/payments/public-key/ MpPublicKeyView

El Checkout API es pago en sitio: la respuesta de MP es síncrona
(approved/rejected/pending se conoce de inmediato, sin redirección).
"""
import json
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from apps.catalogue.models import Category, Product
from apps.orders.models import Order, OrderItem, OrderValue, OrderAddress
from apps.settings_app.models import PaymentGateway
from apps.payments.models import Payment, PaymentGatewayEvent

pytestmark = pytest.mark.integration

INITIATE_V2_URL = '/api/v2/payments/initiate/'
PUBLIC_KEY_URL  = '/api/v2/payments/public-key/'

_VALID_TOKEN          = 'TEST-CARD-TOKEN-ABC123'
_VALID_PAYMENT_METHOD = 'visa'


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def cat_v2(db):
    return Category.objects.create(name='Cat V2', slug='cat-v2', is_active=True)


@pytest.fixture
def prod_v2(db, cat_v2):
    p = Product.objects.create(
        name='Prod V2', slug='prod-v2', sku='V2-001',
        description='', price=Decimal('1500.00'), stock=10,
        is_active=True, is_published=True,
    )
    p.categories.add(cat_v2)
    return p


@pytest.fixture
def orden_v2(db, user, prod_v2):
    """Orden PENDING con OrderValue total=3000."""
    order = Order.objects.create(user=user, status='PENDING')
    OrderItem.objects.create(
        order=order, product_name=prod_v2.name, sku=prod_v2.sku,
        unit_price=prod_v2.price, quantity=2,
        subtotal=prod_v2.price * 2,
    )
    OrderValue.objects.create(
        order=order, subtotal=Decimal('3000.00'),
        tax=Decimal('0.00'), shipping_cost=Decimal('0.00'),
        discount=Decimal('0.00'), total=Decimal('3000.00'),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='Test User',
        street='Av. Reforma 1', city='CDMX',
        state='Ciudad de Mexico', zip_code='06600',
    )
    return order


@pytest.fixture
def mp_gw(db, admin_user):
    """Gateway MERCADOPAGO activo con public_key y access_token falsos."""
    gw = PaymentGateway(
        name='MP CheckoutAPI Test',
        gateway='MERCADOPAGO',
        is_active=True,
    )
    gw.set_credentials({
        'access_token': 'TEST-ACCESS-TOKEN-V2-FAKE',
        'public_key':   'TEST-PUBLIC-KEY-V2-FAKE',
    })
    gw.save()
    return gw


def _make_mp_payment_mock(status='approved', status_detail='accredited',
                          mp_status_code=201, amount=3000.00, installments=1):
    """Devuelve un mock del SDK de MP configurado para payment().create()."""
    mock_mp = MagicMock()
    sdk = MagicMock()
    mock_mp.SDK.return_value = sdk
    sdk.payment.return_value.create.return_value = {
        'status': mp_status_code,
        'response': {
            'id':                 99001,
            'status':             status,
            'status_detail':      status_detail,
            'transaction_amount': amount,
            'installments':       installments,
        },
    }
    return mock_mp


def _valid_payload(order_number, **extra):
    payload = {
        'order_number':     order_number,
        'token':            _VALID_TOKEN,
        'payment_method_id': _VALID_PAYMENT_METHOD,
        'installments':     1,
    }
    payload.update(extra)
    return payload


# =============================================================================
# POST /api/v2/payments/initiate/ — autenticación y validación
# =============================================================================

class TestCheckoutApiAuth:

    def test_sin_auth_retorna_401(self, api_client, db):
        res = api_client.post(INITIATE_V2_URL, {}, format='json')
        assert res.status_code == 401

    def test_payload_vacio_retorna_400(self, auth_client, db):
        res = auth_client.post(INITIATE_V2_URL, {}, format='json')
        assert res.status_code == 400

    def test_token_faltante_retorna_400(self, auth_client, orden_v2, mp_gw, db):
        res = auth_client.post(INITIATE_V2_URL, {
            'order_number':      orden_v2.order_number,
            'payment_method_id': _VALID_PAYMENT_METHOD,
        }, format='json')
        assert res.status_code == 400

    def test_payment_method_faltante_retorna_400(self, auth_client, orden_v2, mp_gw, db):
        res = auth_client.post(INITIATE_V2_URL, {
            'order_number': orden_v2.order_number,
            'token':        _VALID_TOKEN,
        }, format='json')
        assert res.status_code == 400


# =============================================================================
# POST /api/v2/payments/initiate/ — flujos de negocio
# =============================================================================

class TestCheckoutApiOrden:

    def test_orden_no_existe_retorna_404(self, auth_client, mp_gw, db):
        with patch('apps.payments.gateways.mercadopago.mercadopago',
                   _make_mp_payment_mock()):
            res = auth_client.post(INITIATE_V2_URL, _valid_payload('PY-NO-EXISTE'),
                                   format='json')
        assert res.status_code == 404
        assert res.json()['codigo_error'] == 'ORDER_NOT_FOUND'

    def test_orden_de_otro_usuario_retorna_404(
        self, auth_client, orden_v2, mp_gw, db, django_user_model
    ):
        other = django_user_model.objects.create_user(
            username='otro', email='otro@test.mx', password='Otro1234!',
        )
        auth_client.force_authenticate(user=other)
        with patch('apps.payments.gateways.mercadopago.mercadopago',
                   _make_mp_payment_mock()):
            res = auth_client.post(INITIATE_V2_URL,
                                   _valid_payload(orden_v2.order_number),
                                   format='json')
        assert res.status_code == 404
        assert res.json()['codigo_error'] == 'ORDER_NOT_FOUND'

    def test_orden_no_pending_retorna_404(self, auth_client, orden_v2, mp_gw, db):
        orden_v2.status = 'PAID'
        orden_v2.save()
        with patch('apps.payments.gateways.mercadopago.mercadopago',
                   _make_mp_payment_mock()):
            res = auth_client.post(INITIATE_V2_URL,
                                   _valid_payload(orden_v2.order_number),
                                   format='json')
        assert res.status_code == 404
        assert res.json()['codigo_error'] == 'ORDER_NOT_FOUND'

    def test_amount_mismatch_retorna_422(self, auth_client, orden_v2, mp_gw, db):
        with patch('apps.payments.gateways.mercadopago.mercadopago',
                   _make_mp_payment_mock()):
            res = auth_client.post(INITIATE_V2_URL, _valid_payload(
                orden_v2.order_number,
                expected_amount='9999.00',
            ), format='json')
        assert res.status_code == 422
        assert res.json()['codigo_error'] == 'AMOUNT_MISMATCH'

    def test_amount_correcto_pasa_validacion(self, auth_client, orden_v2, mp_gw, db):
        with patch('apps.payments.gateways.mercadopago.mercadopago',
                   _make_mp_payment_mock()):
            res = auth_client.post(INITIATE_V2_URL, _valid_payload(
                orden_v2.order_number,
                expected_amount='3000.00',
            ), format='json')
        assert res.status_code == 201


# =============================================================================
# POST /api/v2/payments/initiate/ — estados de MP
# =============================================================================

class TestCheckoutApiMpStatus:

    def test_pago_aprobado_retorna_201(self, auth_client, orden_v2, mp_gw, db):
        with patch('apps.payments.gateways.mercadopago.mercadopago',
                   _make_mp_payment_mock('approved', 'accredited')):
            res = auth_client.post(INITIATE_V2_URL,
                                   _valid_payload(orden_v2.order_number),
                                   format='json')
        assert res.status_code == 201
        data = res.json()
        assert data['status'] == 'approved'
        assert data['status_detail'] == 'accredited'
        assert data['gateway_payment_id'] == '99001'
        assert data['order_number'] == orden_v2.order_number

    def test_pago_rechazado_retorna_200(self, auth_client, orden_v2, mp_gw, db):
        with patch('apps.payments.gateways.mercadopago.mercadopago',
                   _make_mp_payment_mock('rejected', 'cc_rejected_insufficient_amount')):
            res = auth_client.post(INITIATE_V2_URL,
                                   _valid_payload(orden_v2.order_number),
                                   format='json')
        assert res.status_code == 200
        data = res.json()
        assert data['status'] == 'rejected'
        assert data['status_detail'] == 'cc_rejected_insufficient_amount'

    def test_pago_pendiente_retorna_200(self, auth_client, orden_v2, mp_gw, db):
        with patch('apps.payments.gateways.mercadopago.mercadopago',
                   _make_mp_payment_mock('pending', 'pending_contingency')):
            res = auth_client.post(INITIATE_V2_URL,
                                   _valid_payload(orden_v2.order_number),
                                   format='json')
        assert res.status_code == 200
        data = res.json()
        assert data['status'] == 'pending'

    def test_gateway_error_retorna_502(self, auth_client, orden_v2, mp_gw, db):
        with patch('apps.payments.gateways.mercadopago.mercadopago',
                   _make_mp_payment_mock(mp_status_code=400)):
            res = auth_client.post(INITIATE_V2_URL,
                                   _valid_payload(orden_v2.order_number),
                                   format='json')
        assert res.status_code == 502
        assert res.json()['codigo_error'] == 'GATEWAY_ERROR'


# =============================================================================
# POST /api/v2/payments/initiate/ — efectos en base de datos
# =============================================================================

class TestCheckoutApiDB:

    def test_aprobado_crea_payment_approved(self, auth_client, orden_v2, mp_gw, db):
        with patch('apps.payments.gateways.mercadopago.mercadopago',
                   _make_mp_payment_mock('approved', 'accredited')):
            auth_client.post(INITIATE_V2_URL,
                             _valid_payload(orden_v2.order_number),
                             format='json')
        payment = Payment.objects.get(order=orden_v2)
        assert payment.status == 'APPROVED'
        assert payment.gateway_payment_id == '99001'
        assert payment.gateway == 'MERCADOPAGO'
        assert payment.preference_id is None   # Checkout API nunca usa preference

    def test_aprobado_actualiza_orden_a_paid(self, auth_client, orden_v2, mp_gw, db):
        with patch('apps.payments.gateways.mercadopago.mercadopago',
                   _make_mp_payment_mock('approved', 'accredited')):
            auth_client.post(INITIATE_V2_URL,
                             _valid_payload(orden_v2.order_number),
                             format='json')
        orden_v2.refresh_from_db()
        assert orden_v2.status == 'PAID'

    def test_rechazado_crea_payment_failed_orden_sigue_pending(
        self, auth_client, orden_v2, mp_gw, db
    ):
        with patch('apps.payments.gateways.mercadopago.mercadopago',
                   _make_mp_payment_mock('rejected', 'cc_rejected_other_reason')):
            auth_client.post(INITIATE_V2_URL,
                             _valid_payload(orden_v2.order_number),
                             format='json')
        payment = Payment.objects.get(order=orden_v2)
        assert payment.status == 'FAILED'
        orden_v2.refresh_from_db()
        assert orden_v2.status == 'PENDING'

    def test_aprobado_registra_evento_payment_approved(
        self, auth_client, orden_v2, mp_gw, db
    ):
        with patch('apps.payments.gateways.mercadopago.mercadopago',
                   _make_mp_payment_mock('approved', 'accredited')):
            auth_client.post(INITIATE_V2_URL,
                             _valid_payload(orden_v2.order_number),
                             format='json')
        payment = Payment.objects.get(order=orden_v2)
        event = PaymentGatewayEvent.objects.filter(
            payment=payment, event_type='PAYMENT_APPROVED'
        ).first()
        assert event is not None
        body = json.loads(event.raw_body)
        assert body['source'] == 'checkout_api'
        assert body['gateway_payment_id'] == '99001'

    def test_pendiente_crea_payment_pending(self, auth_client, orden_v2, mp_gw, db):
        with patch('apps.payments.gateways.mercadopago.mercadopago',
                   _make_mp_payment_mock('pending', 'pending_contingency')):
            auth_client.post(INITIATE_V2_URL,
                             _valid_payload(orden_v2.order_number),
                             format='json')
        payment = Payment.objects.get(order=orden_v2)
        assert payment.status == 'PENDING'
        orden_v2.refresh_from_db()
        assert orden_v2.status == 'PENDING'


# =============================================================================
# POST /api/v2/payments/initiate/ — seguridad BR-009
# =============================================================================

class TestCheckoutApiSeguridad:

    def test_br009_credenciales_no_en_respuesta(
        self, auth_client, orden_v2, mp_gw, db
    ):
        """BR-009: access_token y public_key del gateway NUNCA en la respuesta."""
        with patch('apps.payments.gateways.mercadopago.mercadopago',
                   _make_mp_payment_mock('approved')):
            res = auth_client.post(INITIATE_V2_URL,
                                   _valid_payload(orden_v2.order_number),
                                   format='json')
        body_str = json.dumps(res.json())
        assert 'TEST-ACCESS-TOKEN-V2-FAKE' not in body_str
        assert 'TEST-PUBLIC-KEY-V2-FAKE'   not in body_str
        assert 'access_token'              not in body_str

    def test_cuotas_e_issuer_opcionales_pasados_al_gateway(
        self, auth_client, orden_v2, mp_gw, db
    ):
        """Los campos opcionales llegan al gateway sin romper la respuesta."""
        with patch('apps.payments.gateways.mercadopago.mercadopago',
                   _make_mp_payment_mock('approved', installments=3)):
            res = auth_client.post(INITIATE_V2_URL, _valid_payload(
                orden_v2.order_number,
                installments=3,
                issuer_id='12345',
                payer_email='comprador@test.mx',
                payer_identification_type='CURP',
                payer_identification_number='MEMP840321HDFRNSO',
            ), format='json')
        assert res.status_code == 201
        assert res.json()['installments'] == 3


# =============================================================================
# GET /api/v2/payments/public-key/
# =============================================================================

class TestMpPublicKey:

    def test_sin_auth_retorna_401(self, api_client, db):
        res = api_client.get(PUBLIC_KEY_URL)
        assert res.status_code == 401

    def test_retorna_public_key(self, auth_client, mp_gw, db):
        res = auth_client.get(PUBLIC_KEY_URL)
        assert res.status_code == 200
        data = res.json()
        assert 'public_key' in data
        assert data['public_key'] == 'TEST-PUBLIC-KEY-V2-FAKE'

    def test_sin_gateway_activo_retorna_503(self, auth_client, db):
        res = auth_client.get(PUBLIC_KEY_URL)
        assert res.status_code == 503
        assert res.json()['codigo_error'] == 'GATEWAY_NOT_CONFIGURED'

    def test_br009_access_token_no_en_respuesta(self, auth_client, mp_gw, db):
        """BR-009: la public_key va al frontend; el access_token NUNCA."""
        res = auth_client.get(PUBLIC_KEY_URL)
        body_str = json.dumps(res.json())
        assert 'TEST-ACCESS-TOKEN-V2-FAKE' not in body_str
        assert 'access_token' not in body_str


# =============================================================================
# additional_info — calidad de integracion MercadoPago
# (Payment Approval + Security: enviar datos del comprador mejora la
#  aprobacion y alimenta el motor antifraude de MP)
# =============================================================================

class TestCheckoutApiAdditionalInfo:
    """El pago debe enviar additional_info (items, payer, envio) a MP."""

    def _make_gateway(self):
        from apps.payments.gateways.mercadopago import MercadoPagoGateway
        return MercadoPagoGateway.__new__(MercadoPagoGateway)

    def _capture_payload(self, order):
        captured = {}
        sdk = MagicMock()

        def _create(payload):
            captured['payload'] = payload
            return {
                'status': 201,
                'response': {
                    'id': 77001, 'status': 'approved',
                    'status_detail': 'accredited',
                    'transaction_amount': 3000.00, 'installments': 1,
                },
            }

        sdk.payment.return_value.create.side_effect = _create
        with patch('apps.payments.gateways.mercadopago._get_sdk', return_value=sdk):
            self._make_gateway().create_payment(
                order, token=_VALID_TOKEN,
                payment_method_id=_VALID_PAYMENT_METHOD, installments=1,
            )
        return captured['payload']

    def test_envia_additional_info_con_items(self, orden_v2, db):
        payload = self._capture_payload(orden_v2)
        ai = payload.get('additional_info')
        assert ai, 'additional_info debe enviarse a MP'
        assert ai['items'][0]['title'] == 'Prod V2'
        assert ai['items'][0]['quantity'] == 2
        assert ai['items'][0]['unit_price'] == 1500.00

    def test_envia_additional_info_con_payer_nombre(self, orden_v2, db):
        ai = self._capture_payload(orden_v2)['additional_info']
        assert ai['payer']['first_name'] == 'Test'
        assert ai['payer']['last_name'] == 'User'

    def test_envia_additional_info_con_direccion_envio(self, orden_v2, db):
        ai = self._capture_payload(orden_v2)['additional_info']
        addr = ai['shipments']['receiver_address']
        assert addr['zip_code'] == '06600'
        assert addr['city_name'] == 'CDMX'
        assert addr['street_name'] == 'Av. Reforma 1'
