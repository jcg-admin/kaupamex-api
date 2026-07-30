"""
Tests — idempotencia de webhooks via WebhookEvent (T-205, T-206, DEC-BC-04).

WebhookEvent.UNIQUE(gateway, event_id, transmission_id) previene el
procesamiento doble de un evento identico. Los tests verifican que:
  - T-205: PayPal DENIED con mismo transmission_id que COMPLETED previo
           no revierte el pago ya aprobado.
  - T-206: 10 envios del mismo webhook MP producen 1 Payment actualizado
           + 9 respuestas 200 'already_processed'.
"""
import hashlib
import hmac
import json
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from addons.catalogue.models import Category, Product
from addons.orders.models import Order, OrderItem, OrderValue, OrderAddress
from addons.sale.status_projection import order_status
from addons.sale.models import SaleOrder
from addons.payment.models import Payment, WebhookEvent
from addons.payment.models import PaymentGateway
from tests.factories.order_factory import make_order

pytestmark = pytest.mark.integration

MP_WEBHOOK_URL = '/api/v1/payments/webhooks/mercadopago/'
PP_WEBHOOK_URL = '/api/v1/payments/webhooks/paypal/'


# ─── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def cat_idem(db):
    return Category.objects.create(name='Cat Idem', slug='cat-idem', is_active=True)


@pytest.fixture
def mp_gateway_idem(db):
    gw = PaymentGateway(name='MP Idem', gateway='MERCADOPAGO', is_active=True)
    gw.set_credentials({'access_token': 'TEST-TOKEN', 'client_secret': 'SECRET-IDEM'})
    gw.save()
    return gw


@pytest.fixture
def order_mp_pending(db, user, cat_idem):
    """Orden PENDING con Payment MP listo para webhook."""
    prod = Product.objects.create(
        name='Idolo', slug='idolo-idem', sku='IDEM-001',
        description='',
        price=Decimal('500.00'), stock=5,
        is_active=True, is_published=True,
    )
    prod.categories.add(cat_idem)
    order = Order.objects.create(
        user=user, # O2C R8: par canonico — la proyeccion deriva el estado de los ejes.
        sale_order=SaleOrder.objects.create(state=SaleOrder.STATE_SALE),
    )
    OrderItem.objects.create(
        order=order, product_name=prod.name, sku=prod.sku,
        unit_price=prod.price, quantity=1, subtotal=prod.price,
    )
    OrderValue.objects.create(
        order=order, subtotal=Decimal('500.00'), tax=Decimal('69.00'),
        shipping_cost=Decimal('0.00'), discount=Decimal('0.00'),
        total=Decimal('500.00'),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='Test', street='Av 1',
        city='CDMX', state='CMX', zip_code='06600',
    )
    payment = Payment.objects.create(
        order=order, sale_order=order.sale_order, gateway='MERCADOPAGO',
        preference_id='PREF-IDEM-001',
        gateway_payment_id='MP-PAY-IDEM-001',
        status='PENDING', amount=Decimal('500.00'),
    )
    return order, payment


@pytest.fixture
def order_paypal_pending(db, user, cat_idem):
    """Orden PENDING con Payment PayPal listo para webhook."""
    prod = Product.objects.create(
        name='Collar PayPal', slug='collar-paypal-idem', sku='IDEM-PP-001',
        description='',
        price=Decimal('400.00'), stock=5,
        is_active=True, is_published=True,
    )
    prod.categories.add(cat_idem)
    order = Order.objects.create(
        user=user, # O2C R8: par canonico — la proyeccion deriva el estado de los ejes.
        sale_order=SaleOrder.objects.create(state=SaleOrder.STATE_SALE),
    )
    OrderItem.objects.create(
        order=order, product_name=prod.name, sku=prod.sku,
        unit_price=prod.price, quantity=1, subtotal=prod.price,
    )
    OrderValue.objects.create(
        order=order, subtotal=Decimal('400.00'), tax=Decimal('55.17'),
        shipping_cost=Decimal('0.00'), discount=Decimal('0.00'),
        total=Decimal('400.00'),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='PP Test', street='Calle 2',
        city='GDL', state='JAL', zip_code='44100',
    )
    payment = Payment.objects.create(
        order=order, sale_order=order.sale_order, gateway='PAYPAL',
        preference_id='PP-ORDER-IDEM-001',
        gateway_payment_id='PP-CAP-T205',
        status='PENDING', amount=Decimal('400.00'),
    )
    return order, payment


def _mp_signature(secret: str, payment_id: str, request_id: str, ts: str) -> str:
    # Replica el manifest del SDK MercadoPago (WebhookSignatureValidator):
    # data.id en minúsculas, segmentos separados por ';' y ';' final.
    parts = []
    if payment_id:
        parts.append(f'id:{str(payment_id).lower()}')
    if request_id:
        parts.append(f'request-id:{request_id}')
    parts.append(f'ts:{ts}')
    manifest = ';'.join(parts) + ';'
    return hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()


# ─── T-205 — PayPal DENIED con mismo transmission_id no revierte ──────────

class TestWebhookPayPalIdempotencyDenied:

    PP_HEADERS = {
        'HTTP_PAYPAL_AUTH_ALGO':        'SHA256withRSA',
        'HTTP_PAYPAL_CERT_URL':         'https://api.paypal.com/v1/notifications/certs/CERT',
        'HTTP_PAYPAL_TRANSMISSION_SIG': 'SIG-FAKE',
        'HTTP_PAYPAL_TRANSMISSION_TIME': '2026-05-23T00:00:00Z',
    }

    def test_webhook_paypal_denied_after_completed_idempotent(
        self, api_client, order_paypal_pending, db
    ):
        """
        T-205: enviar PAYMENT.CAPTURE.COMPLETED con transmission_id=X → APPROVED.
        Luego enviar PAYMENT.CAPTURE.DENIED con MISMO transmission_id=X.
        Assert: Payment queda APPROVED (el segundo webhook es bloqueado por dedup).
        """
        order, payment = order_paypal_pending
        capture_id      = 'PP-CAP-T205'
        transmission_id = 'TX-IDEM-T205'
        event_id        = 'EVT-T205-COMPLETED'

        completed_payload = {
            'id': event_id,
            'event_type': 'PAYMENT.CAPTURE.COMPLETED',
            'resource': {
                'id':     capture_id,
                'status': 'COMPLETED',
                'amount': {'currency_code': 'MXN', 'value': '400.00'},
            },
        }

        with patch(
            'addons.payment_paypal.gateway.PayPalGateway.verify_webhook_signature',
            return_value=True,
        ):
            res1 = api_client.post(
                PP_WEBHOOK_URL,
                data=json.dumps(completed_payload),
                content_type='application/json',
                **{**self.PP_HEADERS, 'HTTP_PAYPAL_TRANSMISSION_ID': transmission_id},
            )

        assert res1.status_code == 200

        payment.refresh_from_db()
        order.refresh_from_db()
        assert payment.status == 'APPROVED', (
            f'Primer webhook COMPLETED debio aprobar el pago; estado={payment.status}'
        )
        assert order_status(order) == 'PAID', (
            f'Orden debio quedar PAID (DEC-BC-12); estado={order_status(order)}'
        )

        denied_payload = {
            'id': event_id,
            'event_type': 'PAYMENT.CAPTURE.DENIED',
            'resource': {'id': capture_id},
        }

        with patch(
            'addons.payment_paypal.gateway.PayPalGateway.verify_webhook_signature',
            return_value=True,
        ):
            res2 = api_client.post(
                PP_WEBHOOK_URL,
                data=json.dumps(denied_payload),
                content_type='application/json',
                **{**self.PP_HEADERS, 'HTTP_PAYPAL_TRANSMISSION_ID': transmission_id},
            )

        assert res2.status_code == 200
        assert res2.data.get('status') == 'already_processed', (
            f'Segundo webhook con mismo tx_id debio retornar already_processed; '
            f'data={res2.data}'
        )

        payment.refresh_from_db()
        order.refresh_from_db()
        assert payment.status == 'APPROVED', 'DENIED duplicado no debe revertir a FAILED'
        assert order_status(order) == 'PAID', 'Orden no debe regresar de PAID (DEC-BC-12)'


# ─── T-206 — MP replay attack: 10 envíos del mismo webhook ─────────────

class TestWebhookMpReplayAttack:

    def test_webhook_mp_replay_attack(
        self, api_client, order_mp_pending, mp_gateway_idem, db
    ):
        """
        T-206: enviar el mismo webhook MP con data.id=XYZ + X-Request-Id=ABC
        10 veces. Assert: 1 sola Payment actualizada + 9 respuestas already_processed.
        """
        order, payment = order_mp_pending
        secret      = 'SECRET-IDEM'
        payment_id  = 'MP-PAY-IDEM-001'
        request_id  = 'RQ-REPLAY-001'
        ts          = '1716422400'
        sig         = _mp_signature(secret, payment_id, request_id, ts)
        sig_header  = f'ts={ts},v1={sig}'

        payload = json.dumps({
            'type': 'payment',
            'data': {'id': payment_id},
            'external_reference': order.order_number,
        })

        gw_result = MagicMock()
        gw_result.status = 'approved'
        gw_result.amount = Decimal('500.00')

        responses = []
        with patch(
            'addons.payment_mercado_pago.gateway.MercadoPagoGateway.verify_payment',
            return_value=gw_result,
        ):
            for _ in range(10):
                res = api_client.post(
                    MP_WEBHOOK_URL,
                    data=payload,
                    content_type='application/json',
                    HTTP_X_SIGNATURE=sig_header,
                    HTTP_X_REQUEST_ID=request_id,
                )
                responses.append(res)

        assert responses[0].status_code == 200

        for i, res in enumerate(responses[1:], start=1):
            assert res.status_code == 200, f'Peticion {i+1} debio ser 200'
            assert res.data.get('status') == 'already_processed', (
                f'Peticion {i+1} debio retornar already_processed; data={res.data}'
            )

        count = WebhookEvent.objects.filter(
            gateway='MERCADOPAGO', event_id=payment_id, transmission_id=request_id
        ).count()
        assert count == 1, f'Debio haber 1 WebhookEvent; hay {count}'

        payment.refresh_from_db()
        assert payment.status == 'APPROVED'
