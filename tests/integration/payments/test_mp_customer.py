"""
Tests — MercadoPago Customer API integration (TDD)

Cubre:
  Gateway: search_customer_by_email(), create_customer(), get_or_create_customer()
  Service: get_or_create_mp_customer()
  Flow:    initiate_checkout_api_payment() almacena mp_customer_id en User
  View:    GET /api/v2/payments/customer/  MpCustomerView
"""
import json as _json
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from addons.catalogue.models import Category, Product
from addons.orders.models import Order, OrderItem, OrderValue, OrderAddress
from addons.payments.gateways.mercadopago import MercadoPagoGateway
from addons.payments.services import get_or_create_mp_customer
from addons.settings_app.models import PaymentGateway
from addons.users.models import IdentityUser as UserModel

pytestmark = pytest.mark.integration

CUSTOMER_VIEW_URL = '/api/v2/payments/customer/'
INITIATE_V2_URL   = '/api/v2/payments/initiate/'

_MP_CUSTOMER_ID   = 'TEST-CUSTOMER-470183340-cpunOI7UsIHlHr'
_MP_CUSTOMER_ID_2 = 'TEST-CUSTOMER-999999999-abcdefghijk'


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mp_gw(db, admin_user):
    gw = PaymentGateway(
        name='MP Customer Test',
        gateway='MERCADOPAGO',
        is_active=True,
    )
    gw.set_credentials({
        'access_token': 'TEST-ACCESS-TOKEN-CUST-FAKE',
        'public_key':   'TEST-PUBLIC-KEY-CUST-FAKE',
    })
    gw.save()
    return gw


@pytest.fixture
def cat(db):
    return Category.objects.create(name='Cat', slug='cat', is_active=True)


@pytest.fixture
def prod(db, cat):
    p = Product.objects.create(
        name='Prod', slug='prod', sku='CUST-001',
        description='', price=Decimal('500.00'), stock=5,
        is_active=True, is_published=True,
    )
    p.categories.add(cat)
    return p


@pytest.fixture
def orden(db, user, prod):
    order = Order.objects.create(user=user, status='PENDING')
    OrderItem.objects.create(
        order=order, product_name=prod.name, sku=prod.sku,
        unit_price=prod.price, quantity=2,
        subtotal=prod.price * 2,
    )
    OrderValue.objects.create(
        order=order, subtotal=Decimal('1000.00'),
        tax=Decimal('0'), shipping_cost=Decimal('0'),
        discount=Decimal('0'), total=Decimal('1000.00'),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='Test User',
        street='Av. Reforma 1', city='CDMX',
        state='Ciudad de Mexico', zip_code='06600',
    )
    return order


def _make_full_mp_mock(
    payment_status='approved',
    payment_detail='accredited',
    payment_http=201,
    customer_found=False,
    customer_id=_MP_CUSTOMER_ID,
    customer_create_http=201,
):
    """
    Mock completo del SDK de MP — cubre customer Y payment en una sola patch.
    """
    mock_mp  = MagicMock()
    sdk      = MagicMock()
    mock_mp.SDK.return_value = sdk

    # customer().search()
    if customer_found:
        search_results = [{'id': customer_id}]
        search_total   = 1
    else:
        search_results = []
        search_total   = 0

    sdk.customer.return_value.search.return_value = {
        'status': 200,
        'response': {
            'paging':  {'limit': 10, 'offset': 0, 'total': search_total},
            'results': search_results,
        },
    }

    # customer().create()
    sdk.customer.return_value.create.return_value = {
        'status': customer_create_http,
        'response': {'id': customer_id} if customer_create_http == 201 else {'message': 'error'},
    }

    # order().create() — Orders API (DEC-ORD-01); create_payment migrado.
    # El estado interno ('approved'/'rejected'/'pending') se traduce al status
    # de Orders del pago anidado en transactions.payments[0].
    _orders_status = {
        'approved': 'processed', 'rejected': 'failed',
        'pending': 'action_required', 'in_process': 'processing',
    }.get(payment_status, 'processed')
    sdk.order.return_value.create.return_value = {
        'status': payment_http,
        'response': {
            'id':     'ORD88001',
            'status': _orders_status,
            'transactions': {'payments': [{
                'id':            88001,
                'status':        _orders_status,
                'status_detail': payment_detail,
                'amount':        '1000.00',
                'payment_method': {'id': 'visa', 'type': 'credit_card',
                                   'installments': 1},
            }]},
        },
    }

    return mock_mp


# =============================================================================
# Gateway — search_customer_by_email
# =============================================================================

class TestGatewaySearchCustomer:

    def test_found_returns_customer_id(self, mp_gw, db):
        gw = MercadoPagoGateway()
        mock = _make_full_mp_mock(customer_found=True)
        with patch('addons.payments.gateways.mercadopago.mercadopago', mock):
            result = gw.search_customer_by_email('buyer@test.mx')
        assert result == _MP_CUSTOMER_ID
        mock.SDK.return_value.customer.return_value.search.assert_called_once_with(
            {'email': 'buyer@test.mx'}
        )

    def test_not_found_returns_none(self, mp_gw, db):
        gw = MercadoPagoGateway()
        mock = _make_full_mp_mock(customer_found=False)
        with patch('addons.payments.gateways.mercadopago.mercadopago', mock):
            result = gw.search_customer_by_email('nobody@test.mx')
        assert result is None

    def test_mp_error_returns_none(self, mp_gw, db):
        gw = MercadoPagoGateway()
        mock_mp = MagicMock()
        sdk     = MagicMock()
        mock_mp.SDK.return_value = sdk
        sdk.customer.return_value.search.return_value = {'status': 500, 'response': {}}
        with patch('addons.payments.gateways.mercadopago.mercadopago', mock_mp):
            result = gw.search_customer_by_email('buyer@test.mx')
        assert result is None


# =============================================================================
# Gateway — create_customer
# =============================================================================

class TestGatewayCreateCustomer:

    def test_success_returns_customer_id(self, mp_gw, db):
        gw = MercadoPagoGateway()
        mock = _make_full_mp_mock(customer_found=False)
        with patch('addons.payments.gateways.mercadopago.mercadopago', mock):
            cid = gw.create_customer('new@test.mx', 'Ana', 'Lopez')
        assert cid == _MP_CUSTOMER_ID
        sdk = mock.SDK.return_value
        call_args = sdk.customer.return_value.create.call_args[0][0]
        assert call_args['email']      == 'new@test.mx'
        assert call_args['first_name'] == 'Ana'
        assert call_args['last_name']  == 'Lopez'

    def test_mp_error_raises_runtime_error(self, mp_gw, db):
        gw = MercadoPagoGateway()
        mock = _make_full_mp_mock(customer_found=False, customer_create_http=400)
        with patch('addons.payments.gateways.mercadopago.mercadopago', mock):
            with pytest.raises(RuntimeError, match='Error al crear customer'):
                gw.create_customer('bad@test.mx')


# =============================================================================
# Gateway — get_or_create_customer
# =============================================================================

class TestGatewayGetOrCreate:

    def test_uses_existing_customer_no_create(self, mp_gw, db):
        gw = MercadoPagoGateway()
        mock = _make_full_mp_mock(customer_found=True)
        with patch('addons.payments.gateways.mercadopago.mercadopago', mock):
            cid = gw.get_or_create_customer('existing@test.mx')
        assert cid == _MP_CUSTOMER_ID
        # create() nunca debe llamarse si ya existe
        mock.SDK.return_value.customer.return_value.create.assert_not_called()

    def test_creates_when_not_found(self, mp_gw, db):
        gw = MercadoPagoGateway()
        mock = _make_full_mp_mock(customer_found=False)
        with patch('addons.payments.gateways.mercadopago.mercadopago', mock):
            cid = gw.get_or_create_customer('new@test.mx', 'Luis', 'Reyes')
        assert cid == _MP_CUSTOMER_ID
        mock.SDK.return_value.customer.return_value.create.assert_called_once()


# =============================================================================
# Service — get_or_create_mp_customer
# =============================================================================

class TestGetOrCreateMpCustomerService:

    def test_returns_none_when_no_user(self, db):
        assert get_or_create_mp_customer(None) is None

    def test_returns_existing_id_without_calling_mp(self, user, mp_gw, db):
        user.mp_customer_id = 'CACHED-CUST-ID'
        user.save(update_fields=['mp_customer_id'])

        mock = _make_full_mp_mock()
        with patch('addons.payments.gateways.mercadopago.mercadopago', mock):
            result = get_or_create_mp_customer(user)
        assert result == 'CACHED-CUST-ID'
        mock.SDK.return_value.customer.return_value.search.assert_not_called()

    def test_creates_and_stores_customer_id(self, user, mp_gw, db):
        user.mp_customer_id = ''
        user.save(update_fields=['mp_customer_id'])

        mock = _make_full_mp_mock(customer_found=False)
        with patch('addons.payments.gateways.mercadopago.mercadopago', mock):
            result = get_or_create_mp_customer(user)

        assert result == _MP_CUSTOMER_ID
        user.refresh_from_db()
        assert user.mp_customer_id == _MP_CUSTOMER_ID

    def test_mp_failure_returns_none_not_raises(self, user, mp_gw, db):
        user.mp_customer_id = ''
        user.save(update_fields=['mp_customer_id'])

        mock_mp = MagicMock()
        sdk = MagicMock()
        mock_mp.SDK.return_value = sdk
        sdk.customer.return_value.search.side_effect = Exception('Network error')

        with patch('addons.payments.gateways.mercadopago.mercadopago', mock_mp):
            result = get_or_create_mp_customer(user)

        assert result is None  # no-op, no excepción


# =============================================================================
# Flow — initiate_checkout_api_payment stores customer_id
# =============================================================================

class TestCheckoutApiCustomerIntegration:

    def test_approved_stores_mp_customer_id_on_user(
        self, auth_client, orden, mp_gw, user, db
    ):
        """Pago aprobado → user.mp_customer_id guardado."""
        assert user.mp_customer_id == ''  # precondición
        mock = _make_full_mp_mock(
            payment_status='approved', customer_found=False
        )
        with patch('addons.payments.gateways.mercadopago.mercadopago', mock):
            res = auth_client.post(INITIATE_V2_URL, {
                'order_number':      orden.order_number,
                'token':             'TEST-TOKEN-CUST',
                'payment_method_id': 'visa',
                'installments':      1,
            }, format='json')
        assert res.status_code == 201
        user.refresh_from_db()
        assert user.mp_customer_id == _MP_CUSTOMER_ID

    def test_one_time_token_payment_omits_payer_id(
        self, auth_client, orden, mp_gw, user, db
    ):
        """payer.id NO se envía junto al token de un solo uso del CardForm.

        MP interpreta token + payer.id como cobro a una tarjeta guardada del
        customer y busca el token en sus cards → "Card Token not found" para un
        token nuevo. El pago con token de CardForm debe mandar token + email,
        sin payer.id.
        """
        user.mp_customer_id = ''
        user.save(update_fields=['mp_customer_id'])

        mock = _make_full_mp_mock(customer_found=True)
        with patch('addons.payments.gateways.mercadopago.mercadopago', mock):
            auth_client.post(INITIATE_V2_URL, {
                'order_number':      orden.order_number,
                'token':             'TEST-TOKEN-CUST',
                'payment_method_id': 'visa',
                'installments':      1,
            }, format='json')

        sdk = mock.SDK.return_value
        order_call = sdk.order.return_value.create.call_args[0][0]
        assert 'id' not in order_call['payer']
        assert order_call['payer'].get('email')

    def test_customer_failure_does_not_block_payment(
        self, auth_client, orden, mp_gw, db
    ):
        """Si MP customer falla, el pago igual procede."""
        mock_mp = MagicMock()
        sdk = MagicMock()
        mock_mp.SDK.return_value = sdk
        sdk.customer.return_value.search.side_effect = Exception('timeout')
        sdk.order.return_value.create.return_value = {
            'status': 201,
            'response': {
                'id': 'ORD88001', 'status': 'processed',
                'transactions': {'payments': [{
                    'id': 88001, 'status': 'processed',
                    'status_detail': 'accredited', 'amount': '1000.00',
                    'payment_method': {'id': 'visa', 'type': 'credit_card',
                                       'installments': 1},
                }]},
            },
        }
        with patch('addons.payments.gateways.mercadopago.mercadopago', mock_mp):
            res = auth_client.post(INITIATE_V2_URL, {
                'order_number':      orden.order_number,
                'token':             'TEST-TOKEN-CUST',
                'payment_method_id': 'visa',
                'installments':      1,
            }, format='json')
        assert res.status_code == 201


# =============================================================================
# GET /api/v2/payments/customer/
# =============================================================================

class TestMpCustomerView:

    def test_sin_auth_retorna_401(self, api_client, db):
        res = api_client.get(CUSTOMER_VIEW_URL)
        assert res.status_code == 401

    def test_sin_customer_id_retorna_no_customer(self, auth_client, user, db):
        user.mp_customer_id = ''
        user.save(update_fields=['mp_customer_id'])
        res = auth_client.get(CUSTOMER_VIEW_URL)
        assert res.status_code == 200
        data = res.json()
        assert data['has_customer'] is False
        assert data['mp_customer_id'] == ''

    def test_con_customer_id_retorna_id(self, auth_client, user, db):
        user.mp_customer_id = 'EXISTING-CUST-ID'
        user.save(update_fields=['mp_customer_id'])
        res = auth_client.get(CUSTOMER_VIEW_URL)
        assert res.status_code == 200
        data = res.json()
        assert data['has_customer'] is True
        assert data['mp_customer_id'] == 'EXISTING-CUST-ID'

    def test_br009_access_token_no_en_respuesta(self, auth_client, user, db):
        """BR-009: access_token NUNCA en respuesta, aunque user sea admin."""
        user.mp_customer_id = 'CUST-XYZ'
        user.save(update_fields=['mp_customer_id'])
        res = auth_client.get(CUSTOMER_VIEW_URL)
        body_str = _json.dumps(res.json())
        assert 'access_token' not in body_str
        assert 'TEST-ACCESS-TOKEN' not in body_str
