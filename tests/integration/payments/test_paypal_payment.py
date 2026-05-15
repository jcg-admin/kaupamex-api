"""
Tests — Pago con PayPal (UC-PAY-02)

Nomenclatura Clean Code: el nombre describe qué se testea,
no cuándo se implementó.
"""
import json
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock, PropertyMock

pytestmark = pytest.mark.integration

INITIATE_URL = '/api/v1/payments/initiate/'


@pytest.fixture
def cat_pp(db):
    from apps.catalogue.models import Category
    return Category.objects.create(name='Cat PP', slug='cat-pp', is_active=True)


@pytest.fixture
def prod_pp(db, cat_pp):
    from apps.catalogue.models import Product
    return Product.objects.create(
        name='Collar Yoruba', slug='collar-yoruba', sku='PP-CY-001',
        description='', category=cat_pp,
        price=Decimal('800.00'), stock=5,
        is_active=True, is_published=True,
    )


@pytest.fixture
def orden_paypal(db, auth_user, prod_pp):
    from apps.orders.models import Order, OrderItem, OrderValue, OrderAddress
    order = Order.objects.create(user=auth_user, status='PENDING')
    OrderItem.objects.create(
        order=order, product_name=prod_pp.name,
        sku=prod_pp.sku, unit_price=prod_pp.price,
        quantity=1, subtotal=prod_pp.price,
    )
    OrderValue.objects.create(
        order=order, subtotal=Decimal('800.00'),
        tax=Decimal('110.34'), shipping_cost=Decimal('0.00'),
        discount=Decimal('0.00'), total=Decimal('800.00'),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='Test',
        street='Calle 1', city='CDMX', state='CMX', zip_code='06600',
    )
    return order


@pytest.fixture
def paypal_gateway_activo(db):
    from apps.settings_app.models import PaymentGateway
    gw = PaymentGateway(
        name='PayPal Test', gateway='PAYPAL', is_active=True,
    )
    gw.set_credentials({
        'client_id':     'TEST-CLIENT-ID',
        'client_secret': 'TEST-CLIENT-SECRET',
        'env':           'sandbox',
        'webhook_id':    'WH-TEST-123',
    })
    gw.save()
    return gw


@pytest.fixture
def mock_paypal_api():
    """Mock de todas las llamadas requests a PayPal API."""
    with patch('apps.payments.gateways.paypal.requests') as mock_req:
        # Token endpoint
        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.json.return_value = {'access_token': 'PP-TEST-TOKEN'}

        # Order creation endpoint
        order_resp = MagicMock()
        order_resp.status_code = 201
        order_resp.json.return_value = {
            'id': 'PP-ORDER-123456',
            'status': 'CREATED',
            'links': [
                {'rel': 'self',    'href': 'https://api.sandbox.paypal.com/v2/checkout/orders/PP-ORDER-123456'},
                {'rel': 'approve', 'href': 'https://www.sandbox.paypal.com/checkoutnow?token=PP-ORDER-123456'},
                {'rel': 'capture', 'href': 'https://api.sandbox.paypal.com/v2/checkout/orders/PP-ORDER-123456/capture'},
            ],
        }

        # Capture endpoint
        capture_resp = MagicMock()
        capture_resp.status_code = 201
        capture_resp.json.return_value = {
            'id': 'PP-ORDER-123456',
            'status': 'COMPLETED',
            'purchase_units': [{
                'payments': {
                    'captures': [{
                        'id':     'PP-CAPTURE-789',
                        'status': 'COMPLETED',
                        'amount': {'currency_code': 'MXN', 'value': '800.00'},
                    }]
                }
            }]
        }

        # post se usa para token, order creation y capture
        # Secuenciamos las respuestas
        mock_req.post.side_effect = [token_resp, order_resp, token_resp, capture_resp]
        mock_req.get.return_value.status_code = 200
        yield mock_req


class TestPagoConPayPal:

    def test_iniciar_pago_paypal_crea_payment(
        self, auth_client, orden_paypal, paypal_gateway_activo, mock_paypal_api, db
    ):
        res = auth_client.post(INITIATE_URL, {
            'order_number': orden_paypal.order_number,
            'gateway':      'PAYPAL',
        }, format='json')
        assert res.status_code == 201, res.json()
        data = res.json()
        assert 'checkout_url' in data
        assert 'paypal.com' in data['checkout_url'].lower()

    def test_iniciar_pago_paypal_registra_preference_id(
        self, auth_client, orden_paypal, paypal_gateway_activo, mock_paypal_api, db
    ):
        from apps.payments.models import Payment
        auth_client.post(INITIATE_URL, {
            'order_number': orden_paypal.order_number,
            'gateway':      'PAYPAL',
        }, format='json')
        payment = Payment.objects.get(order=orden_paypal, gateway='PAYPAL')
        assert payment.preference_id == 'PP-ORDER-123456'
        assert payment.status == 'PENDING'

    def test_br009_credenciales_paypal_no_en_respuesta(
        self, auth_client, orden_paypal, paypal_gateway_activo, mock_paypal_api, db
    ):
        """BR-009: las credenciales nunca deben aparecer en la respuesta."""
        res = auth_client.post(INITIATE_URL, {
            'order_number': orden_paypal.order_number,
            'gateway':      'PAYPAL',
        }, format='json')
        resp_str = json.dumps(res.json())
        assert 'TEST-CLIENT-ID'     not in resp_str
        assert 'TEST-CLIENT-SECRET' not in resp_str
        assert 'client_secret'      not in resp_str

    def test_paypal_no_tiene_planes_cuotas(
        self, auth_client, orden_paypal, paypal_gateway_activo, mock_paypal_api, db
    ):
        """PayPal no ofrece MSI — lista vacía."""
        from apps.payments.gateways.paypal import PayPalGateway
        plans = PayPalGateway().get_installment_plans(Decimal('800.00'))
        assert plans == []

    def test_gateway_paypal_es_subclase_de_base_gateway(self, db):
        from apps.payments.gateways.base import BaseGateway
        from apps.payments.gateways.paypal import PayPalGateway
        assert issubclass(PayPalGateway, BaseGateway)
