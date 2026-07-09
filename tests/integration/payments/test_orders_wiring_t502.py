"""
T-502 — Wiring de reembolso/cancelación a Orders API + instrumentación legacy.

Verifica la brecha de cableado que quedaba tras la migración a Orders
(``create_payment`` migrado, pero refund/cancel aún ruteaban por el
Payments API legacy) y la instrumentación ``LEGACY_PAYMENTS_API`` que marca
cada invocación de los code-paths legacy durante la ventana de observación
previa a su retiro.

- ``execute_refund`` rutea a ``gateway.refund_order`` cuando el pago tiene
  ``mp_order_id`` (creado por Orders); a ``gateway.refund`` legacy si no.
- ``AdminCancelPaymentView`` rutea a ``cancel_order`` con ``mp_order_id``;
  a ``cancel_payment`` legacy si no.
- Los helpers legacy emiten un WARNING greppeable ``LEGACY_PAYMENTS_API``.

No hacen red: el gateway está mockeado (MagicMock / patch).
"""
import logging
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from apps.orders.models import Order
from apps.payments.models import Payment
from apps.payments.services import execute_refund
from apps.payments.gateways.mercadopago import _log_legacy_payments_api

pytestmark = pytest.mark.integration

CANCEL_URL = lambda pid: f'/api/v2/admin/payments/{pid}/cancel/'


def _payment(user, *, mp_order_id='', status=Payment.STATUS_APPROVED,
             amount=Decimal('250.00')):
    order = Order.objects.create(user=user, status='PROCESSING')
    return Payment.objects.create(
        order=order,
        gateway=Payment.GATEWAY_MERCADOPAGO,
        gateway_payment_id=f'PAY-{order.pk}',
        mp_order_id=mp_order_id or None,
        preference_id=f'PREF-{order.pk}',
        status=status,
        amount=amount,
    )


def _mock_gateway():
    """MagicMock con refund_order/refund que devuelven un RefundResult-like."""
    gw = MagicMock()
    gw.refund_order.return_value = MagicMock(refund_id='REF-ORD-1')
    gw.refund.return_value = MagicMock(refund_id='REF-LEGACY-1')
    return gw


# ---------------------------------------------------------------------------
# execute_refund — routing Orders vs legacy
# ---------------------------------------------------------------------------

class TestRefundRouting:
    def test_routes_to_orders_when_mp_order_id(self, user, db):
        pago = _payment(user, mp_order_id='ORD01ABC')
        gw = _mock_gateway()

        execute_refund(pago, gateway=gw)

        gw.refund_order.assert_called_once()
        assert gw.refund_order.call_args.kwargs['mp_order_id'] == 'ORD01ABC'
        gw.refund.assert_not_called()

    def test_routes_to_legacy_when_no_mp_order_id(self, user, db):
        pago = _payment(user, mp_order_id='')
        gw = _mock_gateway()

        execute_refund(pago, gateway=gw)

        gw.refund.assert_called_once()
        gw.refund_order.assert_not_called()


# ---------------------------------------------------------------------------
# AdminCancelPaymentView — routing Orders vs legacy
# ---------------------------------------------------------------------------

class TestCancelRouting:
    def test_routes_to_cancel_order_when_mp_order_id(self, admin_client, user, db):
        pago = _payment(user, mp_order_id='ORD01ABC',
                        status=Payment.STATUS_PENDING)
        with patch('apps.payments.views.MercadoPagoGateway') as GW:
            gw = GW.return_value
            res = admin_client.post(CANCEL_URL(pago.pk), {}, format='json')

        assert res.status_code == 200, res.json()
        gw.cancel_order.assert_called_once_with('ORD01ABC')
        gw.cancel_payment.assert_not_called()

    def test_routes_to_legacy_when_no_mp_order_id(self, admin_client, user, db):
        pago = _payment(user, mp_order_id='', status=Payment.STATUS_PENDING)
        with patch('apps.payments.views.MercadoPagoGateway') as GW:
            gw = GW.return_value
            res = admin_client.post(CANCEL_URL(pago.pk), {}, format='json')

        assert res.status_code == 200, res.json()
        gw.cancel_payment.assert_called_once_with(pago.gateway_payment_id)
        gw.cancel_order.assert_not_called()


# ---------------------------------------------------------------------------
# Instrumentación legacy — WARNING greppeable
# ---------------------------------------------------------------------------

class TestLegacyInstrumentation:
    def test_helper_emits_greppable_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger='apps'):
            _log_legacy_payments_api('verify_payment', payment_id='PAY9')
        assert any(
            'LEGACY_PAYMENTS_API' in r.message and 'verify_payment' in r.message
            for r in caplog.records
        ), caplog.text
