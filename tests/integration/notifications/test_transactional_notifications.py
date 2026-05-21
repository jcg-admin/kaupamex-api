"""
Tests — Notificaciones transaccionales (UC-NOT-01..05)

Verifica que notify_* crea Notification in-app y despacha email.
EMAIL_BACKEND=locmem captura emails sin servidor SMTP.

transaction.on_commit se parchea para llamar callbacks inmediatamente:
el fixture db envuelve cada test en una transaccion que se revierte
(nunca commitea), por lo que on_commit nunca dispara sin el parche.
"""
import pytest
from decimal import Decimal
from unittest.mock import patch
from django.test import override_settings
from django.core import mail

from apps.notifications.models import Notification
from apps.notifications.service import (
    notify_order_created,
    notify_order_status_changed,
    notify_shipping_updated,
    notify_return_processed,
    notify_refund_processed,
)

pytestmark = pytest.mark.integration

LOCMEM_SETTINGS = {
    'EMAIL_BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
}

_ON_COMMIT_PATH = 'apps.notifications.service.transaction.on_commit'


# ─── fixtures ─────────────────────────────────────────────────────────────────────────

@pytest.fixture
def order_stub(db, user):
    """Orden mínima para testing; no necesita persistencia real."""
    class _Shipping:
        tracking_number = 'TRACK-999'

    class _Order:
        pk           = 1
        order_number = 'PY-TEST-0001'
        user         = user
        shipping_info = _Shipping()

    return _Order()


# ─── UC-NOT-01 ──────────────────────────────────────────────────────────────────────────────

class TestNotifyOrderCreated:
    @override_settings(**LOCMEM_SETTINGS)
    def test_crea_notification_in_app(self, db, user, order_stub):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            notify_order_created(order_stub, user, Decimal('580.00'))
        assert Notification.objects.filter(
            user=user,
            subject__icontains='PY-TEST-0001',
        ).exists()

    @override_settings(**LOCMEM_SETTINGS)
    def test_despacha_email(self, db, user, order_stub):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            notify_order_created(order_stub, user, Decimal('580.00'))
        assert len(mail.outbox) == 1
        assert 'PY-TEST-0001' in mail.outbox[0].subject

    @override_settings(**LOCMEM_SETTINGS)
    def test_no_crea_nada_si_user_es_none(self, db, order_stub):
        order_stub.user = None
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            notify_order_created(order_stub, None, Decimal('580.00'))
        assert not Notification.objects.filter(subject__icontains='PY-TEST-0001').exists()
        assert len(mail.outbox) == 0

    @override_settings(**LOCMEM_SETTINGS)
    def test_no_envia_email_si_user_sin_email(self, db, user, order_stub):
        user.email = ''
        user.save(update_fields=['email'])
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            notify_order_created(order_stub, user, Decimal('580.00'))
        assert Notification.objects.filter(user=user).exists()
        assert len(mail.outbox) == 0


# ─── UC-NOT-02 ──────────────────────────────────────────────────────────────────────────────

class TestNotifyOrderStatusChanged:
    @override_settings(**LOCMEM_SETTINGS)
    @pytest.mark.parametrize('status', [
        'PAYMENT_CONFIRMED', 'IN_PREPARATION', 'SHIPPED',
        'DELIVERED', 'CANCELLED', 'CANCELLED_TIMEOUT',
    ])
    def test_crea_notification_para_estado_relevante(self, db, user, order_stub, status):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            notify_order_status_changed(order_stub, status)
        assert Notification.objects.filter(user=user).exists()

    @override_settings(**LOCMEM_SETTINGS)
    def test_despacha_email_shipped(self, db, user, order_stub):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            notify_order_status_changed(order_stub, 'SHIPPED')
        assert len(mail.outbox) == 1
        assert 'enviado' in mail.outbox[0].subject.lower()

    @override_settings(**LOCMEM_SETTINGS)
    def test_no_notifica_estado_no_relevante(self, db, user, order_stub):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            notify_order_status_changed(order_stub, 'PROCESSING')
        assert not Notification.objects.filter(user=user).exists()
        assert len(mail.outbox) == 0


# ─── UC-NOT-03 ──────────────────────────────────────────────────────────────────────────────

class TestNotifyShippingUpdated:
    @override_settings(**LOCMEM_SETTINGS)
    def test_crea_notification_y_email(self, db, user, order_stub):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            notify_shipping_updated(
                order_stub, user,
                tracking_number='TRACK-001',
                event_description='Paquete en camino.',
            )
        assert Notification.objects.filter(user=user).exists()
        assert len(mail.outbox) == 1
        assert 'envio' in mail.outbox[0].subject.lower()


# ─── UC-NOT-04 ──────────────────────────────────────────────────────────────────────────────

class TestNotifyReturnProcessed:
    @override_settings(**LOCMEM_SETTINGS)
    @pytest.mark.parametrize('status', ['APPROVED', 'REJECTED'])
    def test_crea_notification_y_email(self, db, user, order_stub, status):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            notify_return_processed(order_stub, user, status, reason='Producto dañado')
        assert Notification.objects.filter(user=user).exists()
        assert len(mail.outbox) == 1


# ─── UC-NOT-05 ──────────────────────────────────────────────────────────────────────────────

class TestNotifyRefundProcessed:
    @override_settings(**LOCMEM_SETTINGS)
    def test_crea_notification_y_email(self, db, user, order_stub):
        with patch(_ON_COMMIT_PATH, side_effect=lambda f: f()):
            notify_refund_processed(order_stub, user, Decimal('580.00'))
        assert Notification.objects.filter(user=user).exists()
        assert len(mail.outbox) == 1
        assert '580' in mail.outbox[0].body
