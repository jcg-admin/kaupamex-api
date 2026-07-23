"""
Tests — Cancelación proactiva de pago (T-CAN).

POST /api/v2/admin/payments/<id>/cancel/  — AdminCancelPaymentView
Cubre: cancel ok, pago no cancelable, 404, 401, 403, error de gateway.
"""
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from addons.orders.models import Order, OrderItem, OrderValue, OrderAddress
from addons.payment.models import Payment

pytestmark = pytest.mark.integration

CANCEL_URL = lambda pid: f'/api/v2/admin/payments/{pid}/cancel/'


def _make_payment(user, status=Payment.STATUS_PENDING, gateway_payment_id='MP-CAN-001'):
    order = Order.objects.create(user=user, status='PENDING')
    OrderItem.objects.create(
        order=order, product_name='Prod CAN', sku=f'CAN-{gateway_payment_id}',
        unit_price=Decimal('200.00'), quantity=1, subtotal=Decimal('200.00'),
    )
    OrderValue.objects.create(
        order=order, subtotal=Decimal('200.00'), tax=Decimal('0'),
        shipping_cost=Decimal('0'), discount=Decimal('0'), total=Decimal('200.00'),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='Test', street='Calle CAN',
        city='CDMX', state='CMX', zip_code='06600',
    )
    return Payment.objects.create(
        order=order, gateway='MERCADOPAGO',
        preference_id=f'PREF-{gateway_payment_id}',
        gateway_payment_id=gateway_payment_id,
        status=status, amount=Decimal('200.00'),
    )


class TestAdminCancelPayment:
    def test_cancel_pending_payment(self, admin_client, user, db):
        payment = _make_payment(user, Payment.STATUS_PENDING, 'MP-CAN-001')
        mp_response = {'status': 200, 'response': {'id': 'MP-CAN-001', 'status': 'cancelled'}}
        with patch('addons.payments.views.MercadoPagoGateway') as MockGW:
            MockGW.return_value.cancel_payment.return_value = mp_response
            resp = admin_client.post(CANCEL_URL(payment.pk))

        assert resp.status_code == 200
        payment.refresh_from_db()
        assert payment.status == Payment.STATUS_CANCELLED

    def test_cancel_returns_payment_data(self, admin_client, user, db):
        payment = _make_payment(user, Payment.STATUS_PENDING, 'MP-CAN-002')
        mp_response = {'status': 200, 'response': {'id': 'MP-CAN-002', 'status': 'cancelled'}}
        with patch('addons.payments.views.MercadoPagoGateway') as MockGW:
            MockGW.return_value.cancel_payment.return_value = mp_response
            resp = admin_client.post(CANCEL_URL(payment.pk))

        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == Payment.STATUS_CANCELLED

    def test_cannot_cancel_approved_payment(self, admin_client, user, db):
        payment = _make_payment(user, Payment.STATUS_APPROVED, 'MP-CAN-003')
        resp = admin_client.post(CANCEL_URL(payment.pk))

        assert resp.status_code == 400
        assert resp.json()['codigo_error'] == 'PAYMENT_NOT_CANCELLABLE'

    def test_cannot_cancel_already_cancelled(self, admin_client, user, db):
        payment = _make_payment(user, Payment.STATUS_CANCELLED, 'MP-CAN-004')
        resp = admin_client.post(CANCEL_URL(payment.pk))

        assert resp.status_code == 400
        assert resp.json()['codigo_error'] == 'PAYMENT_NOT_CANCELLABLE'

    def test_returns_404_for_unknown_payment(self, admin_client, db):
        resp = admin_client.post(CANCEL_URL(99999))
        assert resp.status_code == 404

    def test_requires_authentication(self, api_client, user, db):
        payment = _make_payment(user, Payment.STATUS_PENDING, 'MP-CAN-005')
        resp = api_client.post(CANCEL_URL(payment.pk))
        assert resp.status_code == 401

    def test_requires_admin(self, auth_client, user, db):
        payment = _make_payment(user, Payment.STATUS_PENDING, 'MP-CAN-006')
        resp = auth_client.post(CANCEL_URL(payment.pk))
        assert resp.status_code == 403

    def test_gateway_error_returns_503(self, admin_client, user, db):
        payment = _make_payment(user, Payment.STATUS_PENDING, 'MP-CAN-007')
        with patch('addons.payments.views.MercadoPagoGateway') as MockGW:
            MockGW.return_value.cancel_payment.side_effect = RuntimeError('MP gateway down')
            resp = admin_client.post(CANCEL_URL(payment.pk))

        assert resp.status_code == 503
        assert resp.json()['codigo_error'] == 'GATEWAY_UNAVAILABLE'
        payment.refresh_from_db()
        assert payment.status == Payment.STATUS_PENDING
