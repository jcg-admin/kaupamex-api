"""
Tests — Idempotencia de webhooks via WebhookEvent table (DEC-BC-04)

T-205: test_webhook_paypal_denied_after_completed_idempotent
T-206: test_webhook_mp_replay_attack
"""
import hashlib
import hmac
import json
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from apps.catalogue.models import Category, Product
from apps.orders.models import Order, OrderItem, OrderValue, OrderAddress
from apps.payments.models import Payment, WebhookEvent

pytestmark = pytest.mark.integration

MP_WEBHOOK_URL = '/api/v1/payments/webhooks/mercadopago/'
PP_WEBHOOK_URL = '/api/v1/payments/webhooks/paypal/'


def _make_mp_signature(client_secret: str, payment_id: str, request_id: str, ts: str) -> str:
    manifest = f'id:{payment_id};request-id:{request_id};ts:{ts}'
    return hmac.new(client_secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()


@pytest.fixture
def cat_idm(db):
    return Category.objects.create(name='Cat Idm', slug='cat-idm', is_active=True)


@pytest.fixture
def mp_gateway_idm(db):
    from apps.settings_app.models import PaymentGateway
    gw = PaymentGateway(name='MP IDM', gateway='MERCADOPAGO', is_active=True)
    gw.set_credentials({'access_token': 'TEST-TOKEN', 'client_secret': 'TEST-SECRET'})
    gw.save()
    return gw


@pytest.fixture
def orden_mp_idm(db, user, cat_idm):
    prod = Product.objects.create(
        name='Idm Prod', slug='idm-prod', sku='IDM-001',
        description='', category=cat_idm,
        price=Decimal('500.00'), stock=10,
        is_active=True, is_published=True,
    )
    order = Order.objects.create(user=user, status='PENDING')
    OrderItem.objects.create(
        order=order, product_name=prod.name, sku=prod.sku,
        unit_price=prod.price, quantity=1, subtotal=prod.price,
    )
    OrderValue.objects.create(
        order=order, subtotal=Decimal('500.00'), tax=Decimal('68.97'),
        shipping_cost=Decimal('0.00'), discount=Decimal('0.00'), total=Decimal('500.00'),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='Idm', street='St 1',
        city='CDMX', state='CMX', zip_code='06600',
    )
    payment = Payment.objects.create(
        order=order, gateway='MERCADOPAGO',
        preference_id='PREF-IDM-001',
        gateway_payment_id='MP-IDM-001',
        status='PENDING', amount=Decimal('500.00'),
    )
    return order, payment


@pytest.fixture
def orden_paypal_idm(db, user, cat_idm):
    prod = Product.objects.create(
        name='PP Idm Prod', slug='pp-idm-prod', sku='PP-IDM-001',
        description='', category=cat_idm,
        price=Decimal('300.00'), stock=5,
        is_active=True, is_published=True,
    )
    order = Order.objects.create(user=user, status='PENDING')
    OrderItem.objects.create(
        order=order, product_name=prod.name, sku=prod.sku,
        unit_price=prod.price, quantity=1, subtotal=prod.price,
    )
    OrderValue.objects.create(
        order=order, subtotal=Decimal('300.00'), tax=Decimal('41.38'),
        shipping_cost=Decimal('0.00'), discount=Decimal('0.00'), total=Decimal('300.00'),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='PP Idm', street='St 1',
        city='CDMX', state='CMX', zip_code='06600',
    )
    payment = Payment.objects.create(
        order=order, gateway='PAYPAL',
        preference_id='PP-ORDER-IDM-001',
        gateway_payment_id='PP-CAPTURE-IDM-001',
        status='PENDING', amount=Decimal('300.00'),
    )
    return order, payment


def _pp_headers(transmission_id: str = 'TRANS-IDM-001'):
    return {
        'HTTP_PAYPAL_TRANSMISSION_ID':   transmission_id,
        'HTTP_PAYPAL_TRANSMISSION_SIG':  'SIG-FAKE',
        'HTTP_PAYPAL_TRANSMISSION_TIME': '2026-05-22T00:00:00Z',
        'HTTP_PAYPAL_CERT_URL':          'https://api.sandbox.paypal.com/v1/notifications/certs/CERT',
        'HTTP_PAYPAL_AUTH_ALGO':         'SHA256withRSA',
    }


class TestWebhookEventIdempotency:

    def test_webhook_paypal_denied_after_completed_idempotent(
        self, api_client, orden_paypal_idm, db
    ):
        """
        T-205: PAYMENT.CAPTURE.COMPLETED con TX-001 → APPROVED.
        PAYMENT.CAPTURE.DENIED con MISMO TX-001 → 200 duplicate (idempotente).
        Payment permanece APPROVED.
        """
        order, payment = orden_paypal_idm

        completed_payload = {
            'id': 'EVT-PP-IDM-001',
            'event_type': 'PAYMENT.CAPTURE.COMPLETED',
            'resource': {
                'id': 'PP-CAPTURE-IDM-001',
                'status': 'COMPLETED',
                'amount': {'currency_code': 'MXN', 'value': '300.00'},
                'supplementary_data': {
                    'related_ids': {'order_id': 'PP-ORDER-IDM-001'}
                },
            },
        }
        denied_payload = {
            'id': 'EVT-PP-IDM-001',  # mismo event id
            'event_type': 'PAYMENT.CAPTURE.DENIED',
            'resource': {
                'id': 'PP-CAPTURE-IDM-001',
            },
        }

        with patch(
            'apps.payments.gateways.paypal.PayPalGateway.verify_webhook_signature',
            return_value=True,
        ):
            # Primera entrega: COMPLETED con TX-001
            res1 = api_client.post(
                PP_WEBHOOK_URL,
                data=json.dumps(completed_payload),
                content_type='application/json',
                **_pp_headers('TX-001'),
            )
            assert res1.status_code == 200
            payment.refresh_from_db()
            assert payment.status == 'APPROVED'

            # Segunda entrega: DENIED con MISMO TX-001 (replay del mismo evento)
            res2 = api_client.post(
                PP_WEBHOOK_URL,
                data=json.dumps(denied_payload),
                content_type='application/json',
                **_pp_headers('TX-001'),
            )

        assert res2.status_code == 200
        assert res2.data.get('status') == 'duplicate'
        payment.refresh_from_db()
        assert payment.status == 'APPROVED', (
            'Payment debe permanecer APPROVED — el DENIED con mismo TX era un replay'
        )
        assert WebhookEvent.objects.filter(
            gateway='PAYPAL', event_id='EVT-PP-IDM-001', transmission_id='TX-001'
        ).count() == 1

    def test_webhook_mp_replay_attack(
        self, api_client, orden_mp_idm, mp_gateway_idm, db
    ):
        """
        T-206: enviar el mismo MP webhook (data.id=MP-IDM-001 + request_id=REQ-IDM)
        10 veces. Solo la primera produce procesamiento; las 9 siguientes retornan
        200 duplicate. Un solo WebhookEvent en BD.
        """
        order, payment = orden_mp_idm
        ts         = '1716000000'
        request_id = 'REQ-IDM-REPLAY'
        signature  = _make_mp_signature('TEST-SECRET', 'MP-IDM-001', request_id, ts)

        payload = json.dumps({
            'type': 'payment',
            'data': {'id': 'MP-IDM-001'},
            'external_reference': order.order_number,
        })

        statuses = []
        with patch('apps.payments.gateways.mercadopago.mercadopago') as mock_mp:
            sdk = MagicMock()
            mock_mp.SDK.return_value = sdk
            sdk.payment.return_value.get.return_value = {
                'status': 200,
                'response': {
                    'id': 1, 'status': 'approved',
                    'transaction_amount': 500.00, 'installments': 1,
                },
            }
            for _ in range(10):
                res = api_client.post(
                    MP_WEBHOOK_URL,
                    data=payload,
                    content_type='application/json',
                    HTTP_X_SIGNATURE=f'ts={ts};v1={signature}',
                    HTTP_X_REQUEST_ID=request_id,
                )
                assert res.status_code == 200
                statuses.append(res.data.get('status'))

        # La primera llamada procesa; las restantes son duplicate
        assert statuses[0] == 'processed'
        assert all(s == 'duplicate' for s in statuses[1:]), (
            f'Esperado duplicate para llamadas 2-10, obtenido: {statuses[1:]}'
        )

        # Un solo WebhookEvent en BD
        assert WebhookEvent.objects.filter(
            gateway='MERCADOPAGO',
            event_id='MP-IDM-001',
            transmission_id='REQ-IDM-REPLAY',
        ).count() == 1

        # Payment APPROVED (por la primera entrega)
        payment.refresh_from_db()
        assert payment.status == 'APPROVED'
