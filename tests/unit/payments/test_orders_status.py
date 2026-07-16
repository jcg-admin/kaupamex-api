"""
Tests unitarios del mapeo de estados del Orders API (T-101).

Verifican que el nuevo mapa NO caiga al default ``pending`` para los estados
reales de Orders (defecto del ``MP_STATUS_MAP`` Payments-era), que los estados
``action_required`` se traten como pendientes accionables (no rechazo), y que
los ``status_detail`` de rechazo mapeen a su motivo legible.

Funcion pura: sin BD ni red.
Fuente de verdad: analisis-estados-orders-catalogo.rst.
"""
import pytest

from apps.modules.payments.gateways.orders_status import (
    APPROVED,
    IN_PROCESS,
    PENDING,
    REJECTED,
    ORDER_REJECT_REASONS,
    awaiting_deferred_capture,
    awaiting_offline_payment,
    map_order_payment_status,
    reject_reason,
    requires_challenge,
)

pytestmark = pytest.mark.unit


class TestMapOrderPaymentStatus:
    @pytest.mark.parametrize(
        'status,expected',
        [
            ('processed', APPROVED),        # cobro exitoso (accredited)
            ('processing', IN_PROCESS),     # en proceso / revision manual
            ('created', PENDING),           # creada, sin procesar
            ('action_required', PENDING),   # accionable: no es rechazo
            ('canceled', REJECTED),
            ('failed', REJECTED),           # RECHAZO de Orders
            ('refunded', APPROVED),         # reembolso via webhook
            ('charged_back', REJECTED),     # dinero revertido
        ],
    )
    def test_known_statuses(self, status, expected):
        assert map_order_payment_status(status) == expected

    def test_processed_is_not_pending(self):
        # El bug del mapa Payments-era: processed/accredited -> default pending.
        assert map_order_payment_status('processed', 'accredited') == APPROVED
        assert map_order_payment_status('processed', 'accredited') != PENDING

    def test_unknown_status_is_failsafe_pending(self):
        assert map_order_payment_status('some_new_status') == PENDING
        assert map_order_payment_status('') == PENDING

    def test_status_detail_does_not_change_class(self):
        # status_detail refina el motivo pero no la clase interna.
        assert map_order_payment_status('failed', 'high_risk') == REJECTED
        assert map_order_payment_status('action_required', 'pending_challenge') == PENDING


class TestActionableDetails:
    def test_requires_challenge(self):
        assert requires_challenge('pending_challenge') is True
        assert requires_challenge('accredited') is False
        assert requires_challenge('') is False

    def test_awaiting_offline_payment(self):
        assert awaiting_offline_payment('waiting_payment') is True
        assert awaiting_offline_payment('pending_challenge') is False

    def test_awaiting_deferred_capture(self):
        assert awaiting_deferred_capture('waiting_capture') is True
        assert awaiting_deferred_capture('accredited') is False


class TestRejectReason:
    @pytest.mark.parametrize('detail', list(ORDER_REJECT_REASONS.keys()))
    def test_known_reasons_have_message(self, detail):
        msg = reject_reason(detail)
        assert msg and msg != 'El pago fue rechazado.'

    def test_unknown_reason_falls_back(self):
        assert reject_reason('brand_new_reason') == 'El pago fue rechazado.'
        assert reject_reason('') == 'El pago fue rechazado.'

    def test_insufficient_funds_message(self):
        assert reject_reason('card_insufficient_amount') == 'Fondos insuficientes.'
