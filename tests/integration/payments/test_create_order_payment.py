"""
Tests de create_payment cableado al Orders API (T-201b).

Mockean sdk.order().create con una respuesta representativa de Orders y
verifican: llama a order() (no payment()), envía X-Idempotency-Key, mapea el
pago anidado a PaymentResult (gateway_payment_id=PAY, mp_order_id=ORD, status
via orders_status), y clasifica el rechazo.
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from apps.modules.orders.models import Order, OrderItem, OrderValue, OrderAddress
from apps.modules.payments.gateways.mercadopago import MercadoPagoGateway

pytestmark = pytest.mark.integration


def _make_order(user, total='200.00'):
    order = Order.objects.create(user=user, status='PENDING')
    OrderItem.objects.create(
        order=order, product_name='Smartphone', sku='SKU-201B',
        unit_price=Decimal(total), quantity=1, subtotal=Decimal(total),
    )
    OrderValue.objects.create(
        order=order, subtotal=Decimal(total), tax=Decimal('0'),
        shipping_cost=Decimal('0'), discount=Decimal('0'), total=Decimal(total),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='Juan', street='Calle 1',
        city='CDMX', state='CMX', zip_code='06600',
    )
    return order


def _orders_response(pay_status='processed', pay_detail='accredited', http=201):
    return {
        'status': http,
        'response': {
            'id': 'ORD01ABCDEF',
            'status': 'processed',
            'status_detail': 'accredited',
            'transactions': {
                'payments': [
                    {
                        'id': 'PAY123456',
                        'status': pay_status,
                        'status_detail': pay_detail,
                        'amount': '200.00',
                        'payment_method': {'id': 'visa', 'type': 'credit_card', 'installments': 1},
                    }
                ]
            },
        },
    }


class TestCreateOrderPayment:
    def test_approved_maps_both_ids_and_status(self, user, db):
        order = _make_order(user)
        mock_sdk = MagicMock()
        mock_sdk.order.return_value.create.return_value = _orders_response()
        with patch('apps.modules.payments.gateways.mercadopago._get_sdk', return_value=mock_sdk):
            result = MercadoPagoGateway().create_payment(
                order=order, token='TKN', installments=1,
                payment_method_id='visa', payment_type='credit_card',
            )
        assert result.gateway_payment_id == 'PAY123456'
        assert result.mp_order_id == 'ORD01ABCDEF'
        assert result.status == 'approved'
        assert result.status_detail == 'accredited'
        # usa el Orders API, no el Payments API
        mock_sdk.order.return_value.create.assert_called_once()
        mock_sdk.payment.assert_not_called()

    def test_sends_idempotency_header(self, user, db):
        order = _make_order(user)
        mock_sdk = MagicMock()
        mock_sdk.order.return_value.create.return_value = _orders_response()
        with patch('apps.modules.payments.gateways.mercadopago._get_sdk', return_value=mock_sdk):
            MercadoPagoGateway().create_payment(
                order=order, token='TKN', payment_method_id='visa', payment_type='credit_card',
            )
        _, kwargs = mock_sdk.order.return_value.create.call_args
        ro = kwargs['request_options']
        assert 'X-Idempotency-Key' in ro.custom_headers
        assert ro.custom_headers['X-Idempotency-Key']

    def test_rejected_status(self, user, db):
        order = _make_order(user)
        mock_sdk = MagicMock()
        mock_sdk.order.return_value.create.return_value = _orders_response(
            pay_status='failed', pay_detail='cc_rejected_insufficient_amount',
        )
        with patch('apps.modules.payments.gateways.mercadopago._get_sdk', return_value=mock_sdk):
            result = MercadoPagoGateway().create_payment(
                order=order, token='TKN', payment_method_id='visa', payment_type='credit_card',
            )
        assert result.status == 'rejected'

    def test_http_error_raises(self, user, db):
        order = _make_order(user)
        mock_sdk = MagicMock()
        mock_sdk.order.return_value.create.return_value = {
            'status': 400, 'response': {'message': 'bad request'},
        }
        with patch('apps.modules.payments.gateways.mercadopago._get_sdk', return_value=mock_sdk):
            with pytest.raises(RuntimeError):
                MercadoPagoGateway().create_payment(
                    order=order, token='TKN', payment_method_id='visa', payment_type='credit_card',
                )

    def test_declined_402_returns_rejected_not_raises(self, user, db):
        """H-ORD-09 (T-202): un rechazo del emisor llega como HTTP 402 con la
        order bajo response.data (status=failed). Debe mapearse a
        PaymentResult rejected, NO lanzar RuntimeError (si no, la vista daría
        502 en vez de 200 con el motivo)."""
        order = _make_order(user)
        mock_sdk = MagicMock()
        mock_sdk.order.return_value.create.return_value = {
            'status': 402,
            'response': {
                'errors': [{'code': 'failed', 'message': 'The following transactions failed'}],
                'data': {
                    'id': 'ORDFAIL01', 'status': 'failed', 'status_detail': 'failed',
                    'transactions': {'payments': [{
                        'id': 'PAYFAIL01', 'status': 'failed',
                        'status_detail': 'insufficient_amount', 'amount': '200.00',
                        'payment_method': {'id': 'master', 'type': 'credit_card', 'installments': 1},
                    }]},
                },
            },
        }
        with patch('apps.modules.payments.gateways.mercadopago._get_sdk', return_value=mock_sdk):
            result = MercadoPagoGateway().create_payment(
                order=order, token='TKN', payment_method_id='master', payment_type='credit_card',
            )
        assert result.status == 'rejected'
        assert result.status_detail == 'insufficient_amount'
        assert result.gateway_payment_id == 'PAYFAIL01'
        assert result.mp_order_id == 'ORDFAIL01'
