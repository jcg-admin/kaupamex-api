"""
Tests — Zero Dollar Auth (T-15).

T-15-A: MercadoPagoGateway.zero_dollar_auth()
T-15-B: POST /api/v2/payments/cards/validate/ — ZeroDollarAuthView

ZeroDollarAuth valida una tarjeta sin cargo real:
amount=0, capture=False. Retorna {"valid": True/False} según
si MP devuelve status="approved" o cualquier otro estado.
"""
import pytest
from unittest.mock import patch, MagicMock

from addons.payments.gateways.mercadopago import MercadoPagoGateway

pytestmark = pytest.mark.integration

VALIDATE_URL = '/api/v2/payments/cards/validate/'


# ---------------------------------------------------------------------------
# T-15-A — gateway unit-level (patching _get_sdk)
# ---------------------------------------------------------------------------
class TestZeroDollarAuthGateway:
    def _make_gateway(self):
        gw = MercadoPagoGateway.__new__(MercadoPagoGateway)
        return gw

    def test_approved_result(self):
        gw = self._make_gateway()
        mock_response = {
            'status': 201,
            'response': {'id': 1001, 'status': 'approved'},
        }
        with patch('addons.payments.gateways.mercadopago._get_sdk') as mock_get:
            mock_sdk = MagicMock()
            mock_get.return_value = mock_sdk
            mock_sdk.payment().create.return_value = mock_response
            result = gw.zero_dollar_auth(
                token='card_token_abc',
                payment_method_id='visa',
                payer_email='buyer@example.com',
            )

        assert result['status'] == 'approved'

    def test_payload_has_zero_amount_and_no_capture(self):
        gw = self._make_gateway()
        mock_response = {
            'status': 201,
            'response': {'id': 1002, 'status': 'approved'},
        }
        with patch('addons.payments.gateways.mercadopago._get_sdk') as mock_get:
            mock_sdk = MagicMock()
            mock_get.return_value = mock_sdk
            mock_sdk.payment().create.return_value = mock_response
            gw.zero_dollar_auth(
                token='card_token_abc',
                payment_method_id='visa',
                payer_email='buyer@example.com',
            )

        call_args = mock_sdk.payment().create.call_args[0][0]
        assert call_args['transaction_amount'] == 0
        assert call_args['capture'] is False
        assert call_args['token'] == 'card_token_abc'
        assert call_args['payment_method_id'] == 'visa'
        assert call_args['payer']['email'] == 'buyer@example.com'

    def test_rejected_returns_response(self):
        gw = self._make_gateway()
        mock_response = {
            'status': 201,
            'response': {'id': 1003, 'status': 'rejected'},
        }
        with patch('addons.payments.gateways.mercadopago._get_sdk') as mock_get:
            mock_sdk = MagicMock()
            mock_get.return_value = mock_sdk
            mock_sdk.payment().create.return_value = mock_response
            result = gw.zero_dollar_auth(
                token='bad_token',
                payment_method_id='visa',
                payer_email='buyer@example.com',
            )

        assert result['status'] == 'rejected'

    def test_gateway_error_raises_runtime_error(self):
        gw = self._make_gateway()
        mock_response = {
            'status': 400,
            'response': {'message': 'invalid token'},
        }
        with patch('addons.payments.gateways.mercadopago._get_sdk') as mock_get:
            mock_sdk = MagicMock()
            mock_get.return_value = mock_sdk
            mock_sdk.payment().create.return_value = mock_response
            with pytest.raises(RuntimeError, match='Error al validar tarjeta'):
                gw.zero_dollar_auth(
                    token='bad_token',
                    payment_method_id='visa',
                    payer_email='buyer@example.com',
                )


# ---------------------------------------------------------------------------
# T-15-B — view integration (patches MercadoPagoGateway at view level)
# ---------------------------------------------------------------------------
class TestZeroDollarAuthView:
    def test_approved_card_returns_valid_true(self, auth_client, db):
        with patch('addons.payments.views.MercadoPagoGateway') as MockGW:
            MockGW.return_value.zero_dollar_auth.return_value = {
                'id': 2001, 'status': 'approved',
            }
            resp = auth_client.post(
                VALIDATE_URL,
                {'token': 'tok_abc', 'payment_method_id': 'visa'},
                format='json',
            )

        assert resp.status_code == 200
        assert resp.json()['valid'] is True

    def test_rejected_card_returns_valid_false(self, auth_client, db):
        with patch('addons.payments.views.MercadoPagoGateway') as MockGW:
            MockGW.return_value.zero_dollar_auth.return_value = {
                'id': 2002, 'status': 'rejected',
            }
            resp = auth_client.post(
                VALIDATE_URL,
                {'token': 'tok_bad', 'payment_method_id': 'visa'},
                format='json',
            )

        assert resp.status_code == 200
        assert resp.json()['valid'] is False

    def test_pending_card_returns_valid_false(self, auth_client, db):
        with patch('addons.payments.views.MercadoPagoGateway') as MockGW:
            MockGW.return_value.zero_dollar_auth.return_value = {
                'id': 2003, 'status': 'pending',
            }
            resp = auth_client.post(
                VALIDATE_URL,
                {'token': 'tok_pending', 'payment_method_id': 'visa'},
                format='json',
            )

        assert resp.status_code == 200
        assert resp.json()['valid'] is False

    def test_requires_authentication(self, api_client, db):
        resp = api_client.post(
            VALIDATE_URL,
            {'token': 'tok_abc', 'payment_method_id': 'visa'},
            format='json',
        )
        assert resp.status_code == 401

    def test_missing_token_returns_400(self, auth_client, db):
        resp = auth_client.post(
            VALIDATE_URL,
            {'payment_method_id': 'visa'},
            format='json',
        )
        assert resp.status_code == 400

    def test_missing_payment_method_returns_400(self, auth_client, db):
        resp = auth_client.post(
            VALIDATE_URL,
            {'token': 'tok_abc'},
            format='json',
        )
        assert resp.status_code == 400

    def test_gateway_error_returns_502(self, auth_client, db):
        with patch('addons.payments.views.MercadoPagoGateway') as MockGW:
            MockGW.return_value.zero_dollar_auth.side_effect = RuntimeError(
                'Error al validar tarjeta en MercadoPago: invalid token'
            )
            resp = auth_client.post(
                VALIDATE_URL,
                {'token': 'tok_bad', 'payment_method_id': 'visa'},
                format='json',
            )

        assert resp.status_code == 502
        assert resp.json()['codigo_error'] == 'GATEWAY_ERROR'

    def test_payer_email_uses_authenticated_user(self, auth_client, user, db):
        with patch('addons.payments.views.MercadoPagoGateway') as MockGW:
            MockGW.return_value.zero_dollar_auth.return_value = {
                'id': 2004, 'status': 'approved',
            }
            auth_client.post(
                VALIDATE_URL,
                {'token': 'tok_abc', 'payment_method_id': 'visa'},
                format='json',
            )

        MockGW.return_value.zero_dollar_auth.assert_called_once_with(
            token='tok_abc',
            payment_method_id='visa',
            payer_email=user.email,
        )
