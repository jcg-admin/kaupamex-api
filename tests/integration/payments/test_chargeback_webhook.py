"""
Tests — Webhook de contracargos (T-17-A).

POST /api/v1/payments/webhooks/mercadopago/ con topic=chargebacks.
Cubre: creacion de Chargeback, idempotencia, actualizacion de estado,
pago no encontrado (warning log, 200 igual).
"""
import json
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from apps.addons.orders.models import Order, OrderItem, OrderValue, OrderAddress
from apps.addons.payments.models import Payment, Chargeback

pytestmark = pytest.mark.integration

WEBHOOK_URL = '/api/v1/payments/webhooks/mercadopago/'


def _make_payment(user, amount='500.00'):
    order = Order.objects.create(user=user, status='PROCESSING')
    OrderItem.objects.create(
        order=order, product_name='Prod CB', sku='CB-001',
        unit_price=Decimal(amount), quantity=1, subtotal=Decimal(amount),
    )
    OrderValue.objects.create(
        order=order, subtotal=Decimal(amount), tax=Decimal('0'),
        shipping_cost=Decimal('0'), discount=Decimal('0'), total=Decimal(amount),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='Test', street='Calle CB',
        city='CDMX', state='CMX', zip_code='06600',
    )
    return Payment.objects.create(
        order=order, gateway='MERCADOPAGO',
        preference_id='PREF-CB', gateway_payment_id='MP-CB-001',
        status=Payment.STATUS_APPROVED, amount=Decimal(amount),
    )


def _chargeback_payload(chargeback_id='CB-100', payment_id='MP-CB-001'):
    return json.dumps({
        'type': 'chargebacks',
        'data': {'id': chargeback_id},
        'payment_id': payment_id,
    })


def _mock_chargeback(chargeback_id='CB-100', payment_id='MP-CB-001',
                     amount=500.0, status='pending'):
    return {
        'response': {
            'id': chargeback_id,
            'payment_id': payment_id,
            'amount': amount,
            'status': status,
            'reason_code': 'chargeback_fraud',
            'description': 'Customer claims fraud',
        },
        'status': 200,
    }


class TestChargebackWebhook:

    def test_creates_chargeback_on_valid_webhook(self, api_client, user, db):
        payment = _make_payment(user)
        payload = _chargeback_payload('CB-100', 'MP-CB-001')
        mock_result = _mock_chargeback('CB-100', 'MP-CB-001')

        with patch('apps.addons.payments.webhooks._verify_mp_signature', return_value=True), \
             patch('apps.addons.payments.webhooks.MercadoPagoGateway') as MockGW:
            instance = MockGW.return_value
            instance.get_chargeback.return_value = mock_result
            resp = api_client.post(
                WEBHOOK_URL, data=payload, content_type='application/json',
            )

        assert resp.status_code == 200
        assert Chargeback.objects.filter(
            gateway_chargeback_id='CB-100'
        ).exists()
        cb = Chargeback.objects.get(gateway_chargeback_id='CB-100')
        assert cb.payment == payment
        assert cb.amount == Decimal('500.00')
        assert cb.status == Chargeback.STATUS_PENDING
        assert cb.reason_code == 'chargeback_fraud'

    def test_idempotent_on_duplicate_chargeback(self, api_client, user, db):
        payment = _make_payment(user)
        Chargeback.objects.create(
            payment=payment,
            gateway_chargeback_id='CB-200',
            gateway_payment_id='MP-CB-001',
            amount=Decimal('500.00'),
            status=Chargeback.STATUS_PENDING,
            reason_code='chargeback_fraud',
        )
        payload = _chargeback_payload('CB-200', 'MP-CB-001')
        mock_result = _mock_chargeback('CB-200', 'MP-CB-001')

        with patch('apps.addons.payments.webhooks._verify_mp_signature', return_value=True), \
             patch('apps.addons.payments.webhooks.MercadoPagoGateway') as MockGW:
            instance = MockGW.return_value
            instance.get_chargeback.return_value = mock_result
            resp = api_client.post(
                WEBHOOK_URL, data=payload, content_type='application/json',
            )

        assert resp.status_code == 200
        assert Chargeback.objects.filter(gateway_chargeback_id='CB-200').count() == 1

    def test_returns_200_when_payment_not_found(self, api_client, db):
        payload = _chargeback_payload('CB-300', 'MP-UNKNOWN')
        mock_result = _mock_chargeback('CB-300', 'MP-UNKNOWN')

        with patch('apps.addons.payments.webhooks._verify_mp_signature', return_value=True), \
             patch('apps.addons.payments.webhooks.MercadoPagoGateway') as MockGW:
            instance = MockGW.return_value
            instance.get_chargeback.return_value = mock_result
            resp = api_client.post(
                WEBHOOK_URL, data=payload, content_type='application/json',
            )

        assert resp.status_code == 200

    def test_updates_status_on_chargeback_update(self, api_client, user, db):
        payment = _make_payment(user)
        Chargeback.objects.create(
            payment=payment,
            gateway_chargeback_id='CB-400',
            gateway_payment_id='MP-CB-001',
            amount=Decimal('500.00'),
            status=Chargeback.STATUS_PENDING,
            reason_code='chargeback_fraud',
        )
        payload = _chargeback_payload('CB-400', 'MP-CB-001')
        mock_result = _mock_chargeback('CB-400', 'MP-CB-001', status='lost')

        with patch('apps.addons.payments.webhooks._verify_mp_signature', return_value=True), \
             patch('apps.addons.payments.webhooks.MercadoPagoGateway') as MockGW:
            instance = MockGW.return_value
            instance.get_chargeback.return_value = mock_result
            resp = api_client.post(
                WEBHOOK_URL, data=payload, content_type='application/json',
            )

        assert resp.status_code == 200
        cb = Chargeback.objects.get(gateway_chargeback_id='CB-400')
        assert cb.status == Chargeback.STATUS_LOST
