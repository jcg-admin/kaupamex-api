"""
Tests de las operaciones Orders API del gateway (T-301/T-401/T-402/T-403).

Mockean sdk.order().{get,cancel,refund_transaction,search} y verifican el
mapeo al vocabulario interno, el manejo de error y la forma del body de
reembolso parcial. No hacen red — el SDK está mockeado.
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from apps.addons.payments.gateways.mercadopago import MercadoPagoGateway

pytestmark = pytest.mark.integration

_PATCH = 'apps.addons.payments.gateways.mercadopago._get_sdk'


def _gw():
    return MercadoPagoGateway.__new__(MercadoPagoGateway)


def _order_get_resp(pay_status='processed', pay_detail='accredited',
                    http=200, amount='250.00'):
    return {
        'status': http,
        'response': {
            'id': 'ORD01ABC', 'status': 'processed', 'total_amount': amount,
            'transactions': {'payments': [{
                'id': 'PAY9', 'status': pay_status, 'status_detail': pay_detail,
                'amount': amount,
                'payment_method': {'id': 'visa', 'type': 'credit_card',
                                   'installments': 3},
            }]},
        },
    }


# -------------------------------------------------------------------------
# T-301 — verify_order
# -------------------------------------------------------------------------

class TestVerifyOrder:
    def test_approved_maps_status_and_ids(self):
        sdk = MagicMock()
        sdk.order.return_value.get.return_value = _order_get_resp()
        with patch(_PATCH, return_value=sdk):
            res = _gw().verify_order('ORD01ABC')
        assert res.gateway_payment_id == 'PAY9'
        assert res.status == 'approved'
        assert res.amount == Decimal('250.00')
        assert res.installments == 3
        sdk.order.return_value.get.assert_called_once_with('ORD01ABC')

    def test_action_required_maps_pending_not_rejected(self):
        sdk = MagicMock()
        sdk.order.return_value.get.return_value = _order_get_resp(
            pay_status='action_required', pay_detail='pending_challenge')
        with patch(_PATCH, return_value=sdk):
            res = _gw().verify_order('ORD01ABC')
        assert res.status == 'pending'

    def test_http_error_returns_pending_safe(self):
        sdk = MagicMock()
        sdk.order.return_value.get.return_value = {'status': 404, 'response': {}}
        with patch(_PATCH, return_value=sdk):
            res = _gw().verify_order('ORD-missing')
        assert res.status == 'pending'
        assert res.gateway_payment_id is None


# -------------------------------------------------------------------------
# T-401 — cancel_order
# -------------------------------------------------------------------------

class TestCancelOrder:
    def test_cancel_ok(self):
        sdk = MagicMock()
        sdk.order.return_value.cancel.return_value = {
            'status': 200, 'response': {'id': 'ORD01ABC', 'status': 'canceled'},
        }
        with patch(_PATCH, return_value=sdk):
            out = _gw().cancel_order('ORD01ABC')
        assert out['response']['status'] == 'canceled'
        sdk.order.return_value.cancel.assert_called_once_with('ORD01ABC')

    def test_cancel_error_raises(self):
        sdk = MagicMock()
        sdk.order.return_value.cancel.return_value = {
            'status': 400, 'response': {'message': 'not cancellable'},
        }
        with patch(_PATCH, return_value=sdk):
            with pytest.raises(RuntimeError, match='cancelar la order'):
                _gw().cancel_order('ORD01ABC')


# -------------------------------------------------------------------------
# T-402 — refund_order
# -------------------------------------------------------------------------

class TestRefundOrder:
    def test_total_refund_sends_no_body(self):
        sdk = MagicMock()
        sdk.order.return_value.refund_transaction.return_value = {
            'status': 201,
            'response': {'transactions': {'refunds': [{'id': 'REF1', 'amount': '250.00'}]}},
        }
        with patch(_PATCH, return_value=sdk):
            res = _gw().refund_order('ORD01ABC')
        assert res.refund_id == 'REF1'
        assert res.status == 'approved'
        # total → body None
        args = sdk.order.return_value.refund_transaction.call_args[0]
        assert args[0] == 'ORD01ABC'
        assert args[1] is None

    def test_partial_refund_sends_transactions_body(self):
        sdk = MagicMock()
        sdk.order.return_value.refund_transaction.return_value = {
            'status': 201,
            'response': {'transactions': {'refunds': [{'id': 'REF2', 'amount': '100.00'}]}},
        }
        with patch(_PATCH, return_value=sdk):
            res = _gw().refund_order('ORD01ABC', payment_id='PAY9', amount=Decimal('100.00'))
        body = sdk.order.return_value.refund_transaction.call_args[0][1]
        assert body == {'transactions': [{'id': 'PAY9', 'amount': '100.00'}]}
        assert res.amount == Decimal('100.00')

    def test_refund_error_raises(self):
        sdk = MagicMock()
        sdk.order.return_value.refund_transaction.return_value = {
            'status': 400, 'response': {'message': 'already refunded'},
        }
        with patch(_PATCH, return_value=sdk):
            with pytest.raises(RuntimeError, match='reembolsar la order'):
                _gw().refund_order('ORD01ABC')


# -------------------------------------------------------------------------
# T-403 — search_order
# -------------------------------------------------------------------------

class TestSearchOrder:
    def test_search_returns_results(self):
        sdk = MagicMock()
        sdk.order.return_value.search.return_value = {
            'status': 200,
            'response': {'results': [{'id': 'ORD01ABC', 'external_reference': 'PY-100'}]},
        }
        with patch(_PATCH, return_value=sdk):
            out = _gw().search_order('PY-100')
        assert out['results'][0]['id'] == 'ORD01ABC'
        sdk.order.return_value.search.assert_called_once_with(
            filters={'external_reference': 'PY-100'})

    def test_search_error_returns_empty(self):
        sdk = MagicMock()
        sdk.order.return_value.search.return_value = {'status': 500, 'response': {}}
        with patch(_PATCH, return_value=sdk):
            out = _gw().search_order('PY-100')
        assert out == {}
