"""
test_payment_methods.py — UC-PAY-15: Obtener métodos de pago disponibles.

GET /api/v2/payments/methods/
"""
import pytest
from unittest.mock import patch, MagicMock

ENDPOINT = '/api/v2/payments/methods/'

MOCK_MP_RESPONSE = [
    {
        'id': 'visa',
        'name': 'Visa',
        'payment_type_id': 'credit_card',
        'status': 'active',
        'thumbnail': 'http://example.com/visa.png',
        'secure_thumbnail': 'https://example.com/visa.png',
        'min_allowed_amount': 1,
        'max_allowed_amount': 60000,
        'accreditation_time': 2880,
    },
    {
        'id': 'oxxo',
        'name': 'OXXO',
        'payment_type_id': 'ticket',
        'status': 'active',
        'thumbnail': 'http://example.com/oxxo.png',
        'secure_thumbnail': 'https://example.com/oxxo.png',
        'min_allowed_amount': 5,
        'max_allowed_amount': 10000,
        'accreditation_time': 2880,
    },
    {
        'id': 'clabe',
        'name': 'Transferencia bancaria',
        'payment_type_id': 'bank_transfer',
        'status': 'active',
        'thumbnail': 'http://example.com/clabe.png',
        'secure_thumbnail': 'https://example.com/clabe.png',
        'min_allowed_amount': 1,
        'max_allowed_amount': 100000,
        'accreditation_time': 60,
    },
    {
        'id': 'inactive_method',
        'name': 'Método inactivo',
        'payment_type_id': 'ticket',
        'status': 'inactive',
        'thumbnail': '',
        'secure_thumbnail': '',
        'min_allowed_amount': 1,
        'max_allowed_amount': 1000,
        'accreditation_time': 0,
    },
]

MP_SDK_PATH = 'apps.payments.gateways.mercadopago._get_sdk'


@pytest.mark.django_db(transaction=True)
class TestMpPaymentMethodsView:

    def test_requires_auth(self, api_client):
        resp = api_client.get(ENDPOINT)
        assert resp.status_code == 401

    def test_returns_active_methods(self, auth_client):
        sdk_mock = MagicMock()
        sdk_mock.payment_methods.return_value.list_all.return_value = {
            'status': 200,
            'response': MOCK_MP_RESPONSE,
        }
        with patch(MP_SDK_PATH, return_value=sdk_mock):
            resp = auth_client.get(ENDPOINT)
        assert resp.status_code == 200
        data = resp.json()
        ids = [m['id'] for m in data]
        assert 'inactive_method' not in ids
        assert 'visa' in ids
        assert 'oxxo' in ids
        assert 'clabe' in ids

    def test_response_shape(self, auth_client):
        sdk_mock = MagicMock()
        sdk_mock.payment_methods.return_value.list_all.return_value = {
            'status': 200,
            'response': MOCK_MP_RESPONSE,
        }
        with patch(MP_SDK_PATH, return_value=sdk_mock):
            resp = auth_client.get(ENDPOINT)
        method = next(m for m in resp.json() if m['id'] == 'oxxo')
        assert method['name'] == 'OXXO'
        assert method['payment_type_id'] == 'ticket'
        assert 'thumbnail' in method
        assert 'secure_thumbnail' in method
        assert 'min_allowed_amount' in method
        assert 'max_allowed_amount' in method
        assert 'accreditation_time' in method

    def test_gateway_not_configured_returns_503(self, auth_client):
        with patch(MP_SDK_PATH, side_effect=ValueError('No active PaymentGateway')):
            resp = auth_client.get(ENDPOINT)
        assert resp.status_code == 503
        assert resp.json()['codigo_error'] == 'GATEWAY_NOT_CONFIGURED'

    def test_mp_api_error_returns_empty_list(self, auth_client):
        sdk_mock = MagicMock()
        sdk_mock.payment_methods.return_value.list_all.return_value = {
            'status': 500,
            'response': {},
        }
        with patch(MP_SDK_PATH, return_value=sdk_mock):
            resp = auth_client.get(ENDPOINT)
        assert resp.status_code == 200
        assert resp.json() == []
