"""
Tests — Pago con PayPal (UC-PAY-02)

Nomenclatura Clean Code: el nombre describe qué se testea,
no cuándo se implementó.
"""
import json
import pytest
from addons.sale.models import SaleOrder, SaleOrderLine
from decimal import Decimal
from unittest.mock import patch, MagicMock
from addons.catalogue.models import Category, Product
from addons.delivery.models import DeliveryAddress
from addons.payment.models import PaymentGateway
from addons.payment.models import Payment
from addons.payment_paypal.gateway import PayPalGateway
from addons.payment.gateways.base import BaseGateway
from tests.factories.order_factory import make_order

pytestmark = pytest.mark.integration

INITIATE_URL = '/api/v1/payments/initiate/'


@pytest.fixture
def cat_pp(db):
    return Category.objects.create(name='Cat PP', slug='cat-pp', is_active=True)


@pytest.fixture
def prod_pp(db, cat_pp):
    _p = Product.objects.create(
        name='Collar Yoruba', slug='collar-yoruba', sku='PP-CY-001',
        description='',
        price=Decimal('800.00'), stock=5,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_pp)
    return _p


@pytest.fixture
def orden_paypal(db, user, prod_pp):
    """Orden PENDING con una linea de producto (total 800.00).

    El registro de importes aparte de la orden se retiro con el espejo
    (SOL-098): el importe se recalcula desde ``order_line``, no se fija a
    mano.
    """
    order = make_order(user=user, status='PENDING')
    SaleOrderLine.objects.create(
        order=order, product=prod_pp, name=prod_pp.name,
        price_unit=prod_pp.price, product_uom_qty=1,
    )
    DeliveryAddress.objects.create(
        sale_order=order, recipient_name='Test',
        street='Calle 1', city='CDMX', state='CMX', zip_code='06600',
    )
    return order


@pytest.fixture
def paypal_gateway_activo(db):
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
    with patch('addons.payment_paypal.gateway.requests') as mock_req:
        # Token endpoint
        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.json.return_value = {'access_token': 'PP-TEST-TOKEN'}

        # SaleOrder creation endpoint
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
            'order_number': orden_paypal.name,
            'gateway':      'PAYPAL',
        }, format='json')
        assert res.status_code == 201, res.json()
        data = res.json()
        assert 'checkout_url' in data
        assert 'paypal.com' in data['checkout_url'].lower()

    def test_iniciar_pago_paypal_registra_preference_id(
        self, auth_client, orden_paypal, paypal_gateway_activo, mock_paypal_api, db
    ):
        auth_client.post(INITIATE_URL, {
            'order_number': orden_paypal.name,
            'gateway':      'PAYPAL',
        }, format='json')
        payment = Payment.objects.get(sale_order=orden_paypal, gateway='PAYPAL')
        assert payment.preference_id == 'PP-ORDER-123456'
        assert payment.status == 'PENDING'

    def test_br009_credenciales_paypal_no_en_respuesta(
        self, auth_client, orden_paypal, paypal_gateway_activo, mock_paypal_api, db
    ):
        """BR-009: las credenciales nunca deben aparecer en la respuesta."""
        res = auth_client.post(INITIATE_URL, {
            'order_number': orden_paypal.name,
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
        plans = PayPalGateway().get_installment_plans(Decimal('800.00'))
        assert plans == []

    def test_gateway_paypal_es_subclase_de_base_gateway(self, db):
        assert issubclass(PayPalGateway, BaseGateway)
