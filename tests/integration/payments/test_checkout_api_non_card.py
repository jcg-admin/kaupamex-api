"""
Tests — MercadoPago non-card payment methods (Checkout API v2)

Covers: OXXO, SPEI (clabe), Paycash, Banamex (banamex), Santander (serfin),
BBVA (bancomer), Cuenta Mercado Pago (account_money).

All use POST /api/v2/payments/initiate/ but WITHOUT a token.
MP responds with external_resource_url / date_of_expiration / transaction_data.
"""
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from apps.catalogue.models import Category, Product
from apps.orders.models import Order, OrderItem, OrderValue, OrderAddress
from apps.settings_app.models import PaymentGateway
from apps.payments.models import Payment

pytestmark = pytest.mark.integration

INITIATE_V2_URL = '/api/v2/payments/initiate/'


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def cat_nc(db):
    return Category.objects.create(name='Cat NC', slug='cat-nc', is_active=True)


@pytest.fixture
def prod_nc(db, cat_nc):
    p = Product.objects.create(
        name='Prod NC', slug='prod-nc', sku='NC-001',
        description='', price=Decimal('500.00'), stock=10,
        is_active=True, is_published=True,
    )
    p.categories.add(cat_nc)
    return p


@pytest.fixture
def orden_nc(db, user, prod_nc):
    order = Order.objects.create(user=user, status='PENDING')
    OrderItem.objects.create(
        order=order, product_name=prod_nc.name, sku=prod_nc.sku,
        unit_price=prod_nc.price, quantity=1,
        subtotal=prod_nc.price,
    )
    OrderValue.objects.create(
        order=order, subtotal=Decimal('500.00'),
        tax=Decimal('0.00'), shipping_cost=Decimal('0.00'),
        discount=Decimal('0.00'), total=Decimal('500.00'),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='Test User',
        street='Av. Insurgentes 1', city='CDMX',
        state='Ciudad de Mexico', zip_code='06600',
    )
    return order


@pytest.fixture
def mp_gw_nc(db, admin_user):
    gw = PaymentGateway(
        name='MP NC Test',
        gateway='MERCADOPAGO',
        is_active=True,
    )
    gw.set_credentials({
        'access_token': 'TEST-ACCESS-NC-FAKE',
        'public_key':   'TEST-PK-NC-FAKE',
    })
    gw.save()
    return gw


def _mp_response(payment_method_id, status='pending',
                 external_resource_url='', date_of_expiration='',
                 transaction_data=None):
    resp = MagicMock()
    resp.__getitem__ = lambda self, key: {
        'status': 201,
        'response': {
            'id': '999888777',
            'status': status,
            'status_detail': 'pending_waiting_payment',
            'transaction_amount': 500.00,
            'installments': 1,
            'payment_method_id': payment_method_id,
            'date_of_expiration': date_of_expiration,
            'transaction_details': {
                'external_resource_url': external_resource_url,
            },
            'transaction_data': transaction_data or {},
        },
    }[key]
    resp.get = lambda key, default=None: {
        'status': 201,
    }.get(key, default)
    return resp


# =============================================================================
# Tests — OXXO
# =============================================================================

@pytest.mark.django_db
def test_oxxo_payment_no_token_required(auth_client, orden_nc, mp_gw_nc):
    mp_mock = MagicMock()
    mp_resp = {
        'status': 201,
        'response': {
            'id': '111222333',
            'status': 'pending',
            'status_detail': 'pending_waiting_payment',
            'transaction_amount': 500.00,
            'installments': 1,
            'date_of_expiration': '2026-07-04T23:59:59.000-06:00',
            'transaction_details': {
                'external_resource_url': 'https://www.mercadopago.com/mlm/payments/ticket/123',
            },
            'transaction_data': {},
        },
    }
    mp_mock.payment.return_value.create.return_value = mp_resp

    with patch('apps.payments.gateways.mercadopago._get_sdk', return_value=mp_mock):
        resp = auth_client.post(INITIATE_V2_URL, {
            'order_number':     orden_nc.order_number,
            'payment_method_id': 'oxxo',
        }, content_type='application/json')

    assert resp.status_code == 200, resp.data
    data = resp.data
    assert data['status'] == 'pending'
    assert 'mercadopago.com' in data['external_resource_url']
    assert data['date_of_expiration'] != ''
    assert Payment.objects.filter(order=orden_nc).exists()


@pytest.mark.django_db
def test_oxxo_token_in_request_is_ignored_gracefully(auth_client, orden_nc, mp_gw_nc):
    """Enviar token con método oxxo no debe romper la validación."""
    mp_mock = MagicMock()
    mp_resp = {
        'status': 201,
        'response': {
            'id': '444555666',
            'status': 'pending',
            'status_detail': 'pending_waiting_payment',
            'transaction_amount': 500.00,
            'installments': 1,
            'date_of_expiration': '2026-07-04T23:59:59.000-06:00',
            'transaction_details': {'external_resource_url': 'https://mp.com/ticket/x'},
            'transaction_data': {},
        },
    }
    mp_mock.payment.return_value.create.return_value = mp_resp

    with patch('apps.payments.gateways.mercadopago._get_sdk', return_value=mp_mock):
        resp = auth_client.post(INITIATE_V2_URL, {
            'order_number':     orden_nc.order_number,
            'payment_method_id': 'oxxo',
            'token':            'some-irrelevant-token',
        }, content_type='application/json')

    assert resp.status_code == 200, resp.data


# =============================================================================
# Tests — SPEI (clabe)
# =============================================================================

@pytest.mark.django_db
def test_spei_returns_clabe_in_transaction_data(auth_client, orden_nc, mp_gw_nc):
    mp_mock = MagicMock()
    mp_resp = {
        'status': 201,
        'response': {
            'id': '777888999',
            'status': 'pending',
            'status_detail': 'pending_waiting_transfer',
            'transaction_amount': 500.00,
            'installments': 1,
            'date_of_expiration': '2026-07-01T23:59:59.000-06:00',
            'transaction_details': {'external_resource_url': ''},
            'transaction_data': {
                'bank_transfer_id': 123456,
                'transaction_id':   654321,
                'financial_institution': '90646',
                'bank_info': {
                    'origin': {'name': 'STP'},
                    'destination': {
                        'name': 'MercadoPago',
                        'account_id': 'CLABE123456789012345678',
                    },
                },
            },
        },
    }
    mp_mock.payment.return_value.create.return_value = mp_resp

    with patch('apps.payments.gateways.mercadopago._get_sdk', return_value=mp_mock):
        resp = auth_client.post(INITIATE_V2_URL, {
            'order_number':     orden_nc.order_number,
            'payment_method_id': 'clabe',
        }, content_type='application/json')

    assert resp.status_code == 200, resp.data
    assert resp.data['status'] == 'pending'
    assert resp.data['transaction_data'] is not None
    clabe_info = resp.data['transaction_data']
    assert 'bank_info' in clabe_info


# =============================================================================
# Tests — Token required for card methods
# =============================================================================

@pytest.mark.django_db
def test_card_method_without_token_returns_400(auth_client, orden_nc, mp_gw_nc):
    resp = auth_client.post(INITIATE_V2_URL, {
        'order_number':     orden_nc.order_number,
        'payment_method_id': 'visa',
    }, content_type='application/json')

    assert resp.status_code == 400
    assert 'token' in str(resp.data)


@pytest.mark.django_db
def test_paycash_payment_no_token(auth_client, orden_nc, mp_gw_nc):
    mp_mock = MagicMock()
    mp_resp = {
        'status': 201,
        'response': {
            'id': '321654987',
            'status': 'pending',
            'status_detail': 'pending_waiting_payment',
            'transaction_amount': 500.00,
            'installments': 1,
            'date_of_expiration': '2026-07-05T23:59:59.000-06:00',
            'transaction_details': {
                'external_resource_url': 'https://www.mercadopago.com/mlm/payments/ticket/456',
            },
            'transaction_data': {},
        },
    }
    mp_mock.payment.return_value.create.return_value = mp_resp

    with patch('apps.payments.gateways.mercadopago._get_sdk', return_value=mp_mock):
        resp = auth_client.post(INITIATE_V2_URL, {
            'order_number':     orden_nc.order_number,
            'payment_method_id': 'paycash',
        }, content_type='application/json')

    assert resp.status_code == 200, resp.data
    assert resp.data['external_resource_url'] != ''


@pytest.mark.django_db
def test_bancomer_atm_no_token(auth_client, orden_nc, mp_gw_nc):
    mp_mock = MagicMock()
    mp_resp = {
        'status': 201,
        'response': {
            'id': '159753486',
            'status': 'pending',
            'status_detail': 'pending_waiting_payment',
            'transaction_amount': 500.00,
            'installments': 1,
            'date_of_expiration': '2026-07-05T23:59:59.000-06:00',
            'transaction_details': {
                'external_resource_url': 'https://www.mercadopago.com/mlm/payments/atm/789',
            },
            'transaction_data': {},
        },
    }
    mp_mock.payment.return_value.create.return_value = mp_resp

    with patch('apps.payments.gateways.mercadopago._get_sdk', return_value=mp_mock):
        resp = auth_client.post(INITIATE_V2_URL, {
            'order_number':     orden_nc.order_number,
            'payment_method_id': 'bancomer',
        }, content_type='application/json')

    assert resp.status_code == 200, resp.data
    assert 'atm' in resp.data['external_resource_url']


@pytest.mark.django_db
def test_account_money_no_token(auth_client, orden_nc, mp_gw_nc):
    """Cuenta Mercado Pago: pago instantáneo sin token."""
    mp_mock = MagicMock()
    mp_resp = {
        'status': 201,
        'response': {
            'id': '246813579',
            'status': 'approved',
            'status_detail': 'accredited',
            'transaction_amount': 500.00,
            'installments': 1,
            'date_of_expiration': '',
            'transaction_details': {'external_resource_url': ''},
            'transaction_data': {},
        },
    }
    mp_mock.payment.return_value.create.return_value = mp_resp

    with patch('apps.payments.gateways.mercadopago._get_sdk', return_value=mp_mock):
        resp = auth_client.post(INITIATE_V2_URL, {
            'order_number':     orden_nc.order_number,
            'payment_method_id': 'account_money',
        }, content_type='application/json')

    assert resp.status_code == 201, resp.data
    assert resp.data['status'] == 'approved'
