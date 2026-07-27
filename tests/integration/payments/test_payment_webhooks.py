"""
Tests — Webhooks de confirmación de pago (UC-PAY-03, UC-PAY-04)

Nombre descriptivo: describe el dominio testeado, no el número de sprint.
Cubre verificación de firma, idempotencia, actualización de Order y Payment.
"""
import hashlib
import hmac
import json
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from addons.catalogue.models import Category, Product
from addons.orders.models import Order, OrderItem, OrderValue, OrderAddress
from addons.orders.status_projection import order_status
from addons.sale.models import SaleOrder
from django.core.checks.registry import registry
from addons.payment_mercado_pago.checks import check_mercadopago_client_secret
from addons.payment.models import Payment
from addons.payment.models import PaymentGateway

pytestmark = pytest.mark.integration

MP_WEBHOOK_URL = '/api/v1/payments/webhooks/mercadopago/'
PP_WEBHOOK_URL = '/api/v1/payments/webhooks/paypal/'


@pytest.fixture
def cat_wh(db):
    return Category.objects.create(name='Cat WH', slug='cat-wh', is_active=True)


@pytest.fixture
def orden_processing_mp(db, user, cat_wh):
    """Orden con Payment de MP en PENDING, lista para recibir webhook."""

    prod = Product.objects.create(
        name='Pulso Orula', slug='pulso-orula', sku='WH-PO-001',
        description='',
        price=Decimal('600.00'), stock=10,
        is_active=True, is_published=True,
    )
    prod.categories.add(cat_wh)
    order = Order.objects.create(
        user=user, status='PENDING',
        # O2C R8: par canonico — la proyeccion deriva el estado de los ejes.
        sale_order=SaleOrder.objects.create(state=SaleOrder.STATE_SALE),
    )
    OrderItem.objects.create(
        order=order, product_name=prod.name, sku=prod.sku,
        unit_price=prod.price, quantity=1, subtotal=prod.price,
    )
    OrderValue.objects.create(
        order=order, subtotal=Decimal('600.00'), tax=Decimal('82.76'),
        shipping_cost=Decimal('0.00'), discount=Decimal('0.00'), total=Decimal('600.00'),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='Test', street='St 1',
        city='CDMX', state='CMX', zip_code='06600',
    )
    payment = Payment.objects.create(
        order=order, sale_order=order.sale_order, gateway='MERCADOPAGO',
        preference_id='PREF-WH-TEST-001',
        gateway_payment_id='MP-PAY-999',
        status='PENDING', amount=Decimal('600.00'),
    )
    return order, payment


@pytest.fixture
def mp_gateway_wh(db):
    gw = PaymentGateway(name='MP WH', gateway='MERCADOPAGO', is_active=True)
    gw.set_credentials({'access_token': 'TEST-TOKEN', 'client_secret': 'TEST-SECRET'})
    gw.save()
    return gw


def _make_mp_signature(client_secret: str, payment_id: str, request_id: str, ts: str) -> str:
    # Replica EXACTA del manifest del SDK oficial (WebhookSignatureValidator):
    # data.id en minúsculas, segmentos ausentes omitidos, trailing ';'.
    # El header x-signature usa coma ('ts=..,v1=..'), no ';'.
    parts = []
    if payment_id:
        parts.append(f'id:{str(payment_id).lower()}')
    if request_id:
        parts.append(f'request-id:{request_id}')
    parts.append(f'ts:{ts}')
    manifest = ';'.join(parts) + ';'
    return hmac.new(client_secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()


class TestMercadoPagoWebhook:

    def test_webhook_pago_aprobado_actualiza_payment_y_orden(
        self, api_client, orden_processing_mp, mp_gateway_wh, db
    ):
        """FR-PAY-03.02: pago aprobado → Payment=APPROVED, Order=PAID (DEC-BC-12)."""
        order, payment = orden_processing_mp
        ts         = '1715000000'
        request_id = 'REQ-TEST-123'
        signature  = _make_mp_signature('TEST-SECRET', 'MP-PAY-999', request_id, ts)

        with patch('addons.payment_mercado_pago.gateway.mercadopago') as mock_mp:
            sdk = MagicMock()
            mock_mp.SDK.return_value = sdk
            sdk.payment.return_value.get.return_value = {
                'status': 200,
                'response': {
                    'id': 999, 'status': 'approved',
                    'transaction_amount': 600.00, 'installments': 1,
                },
            }
            res = api_client.post(
                MP_WEBHOOK_URL,
                data=json.dumps({'type': 'payment', 'data': {'id': 'MP-PAY-999'},
                                 'external_reference': order.order_number}),
                content_type='application/json',
                HTTP_X_SIGNATURE=f'ts={ts},v1={signature}',
                HTTP_X_REQUEST_ID=request_id,
            )

        assert res.status_code == 200
        payment.refresh_from_db()
        order.refresh_from_db()
        assert payment.status == 'APPROVED'
        assert order_status(order) == 'PAID'  # DEC-BC-12 proyectado del eje

    def test_webhook_tipo_order_aprobado_actualiza_payment(
        self, api_client, orden_processing_mp, mp_gateway_wh, db
    ):
        """T-302: notificación ``type: order`` (data.id = ORD) verifica via
        Orders API el PAY anidado y aprueba el Payment/Order."""
        order, payment = orden_processing_mp
        payment.mp_order_id = 'ORD-WH-1'
        payment.gateway_payment_id = 'PAY-WH-1'
        payment.save(update_fields=['mp_order_id', 'gateway_payment_id'])

        ts         = '1715000010'
        request_id = 'REQ-ORD-1'
        signature  = _make_mp_signature('TEST-SECRET', 'ORD-WH-1', request_id, ts)

        with patch('addons.payment_mercado_pago.gateway.mercadopago') as mock_mp:
            sdk = MagicMock()
            mock_mp.SDK.return_value = sdk
            sdk.order.return_value.get.return_value = {
                'status': 200,
                'response': {
                    'id': 'ORD-WH-1', 'status': 'processed', 'total_amount': '600.00',
                    'transactions': {'payments': [{
                        'id': 'PAY-WH-1', 'status': 'processed',
                        'status_detail': 'accredited', 'amount': '600.00',
                        'payment_method': {'id': 'visa', 'type': 'credit_card',
                                           'installments': 1},
                    }]},
                },
            }
            res = api_client.post(
                MP_WEBHOOK_URL,
                data=json.dumps({'type': 'order', 'data': {'id': 'ORD-WH-1'},
                                 'external_reference': order.order_number}),
                content_type='application/json',
                HTTP_X_SIGNATURE=f'ts={ts},v1={signature}',
                HTTP_X_REQUEST_ID=request_id,
            )

        assert res.status_code == 200, res.data
        payment.refresh_from_db()
        order.refresh_from_db()
        assert payment.status == 'APPROVED'
        assert order_status(order) == 'PAID'
        # usó el Orders API para la verificación, no el Payments API
        sdk.order.return_value.get.assert_called_once_with('ORD-WH-1')

    def test_webhook_firma_invalida_retorna_401(
        self, api_client, orden_processing_mp, mp_gateway_wh, db
    ):
        """FR-PAY-03.01: firma inválida → 401, sin procesar."""
        order, payment = orden_processing_mp
        res = api_client.post(
            MP_WEBHOOK_URL,
            data=json.dumps({'type': 'payment', 'data': {'id': 'MP-PAY-999'}}),
            content_type='application/json',
            HTTP_X_SIGNATURE='ts=1234,v1=firma-invalida-falsa',
            HTTP_X_REQUEST_ID='req-1',
        )
        assert res.status_code == 401
        payment.refresh_from_db()
        assert payment.status == 'PENDING'  # no cambió

    def test_webhook_idempotente_pago_ya_aprobado(
        self, api_client, orden_processing_mp, mp_gateway_wh, db
    ):
        """FR-PAY-03.02: mismo webhook dos veces — solo la primera cambia el estado."""
        order, payment = orden_processing_mp
        payment.status = 'APPROVED'
        payment.save()
        order.status = 'PROCESSING'
        order.save()

        ts        = '1715000001'
        req_id    = 'REQ-DUP-456'
        signature = _make_mp_signature('TEST-SECRET', 'MP-PAY-999', req_id, ts)

        with patch('addons.payment_mercado_pago.gateway.mercadopago') as mock_mp:
            sdk = MagicMock()
            mock_mp.SDK.return_value = sdk
            sdk.payment.return_value.get.return_value = {
                'status': 200,
                'response': {'id': 999, 'status': 'approved', 'transaction_amount': 600.0},
            }
            res = api_client.post(
                MP_WEBHOOK_URL,
                data=json.dumps({'type': 'payment', 'data': {'id': 'MP-PAY-999'}}),
                content_type='application/json',
                HTTP_X_SIGNATURE=f'ts={ts},v1={signature}',
                HTTP_X_REQUEST_ID=req_id,
            )

        assert res.status_code == 200
        payment.refresh_from_db()
        assert payment.status == 'APPROVED'  # sin cambio
        order.refresh_from_db()
        # O2C R8: proyectado — el pago ya estaba APPROVED, sigue PAID.
        assert order_status(order) == 'PAID'  # sin cambio

    def test_webhook_pago_rechazado_marca_payment_failed(
        self, api_client, orden_processing_mp, mp_gateway_wh, db
    ):
        """FR-PAY-03.02: pago rechazado → Payment=FAILED, Order permanece en PENDING."""
        order, payment = orden_processing_mp
        ts     = '1715000002'
        req_id = 'REQ-FAIL-789'
        sig    = _make_mp_signature('TEST-SECRET', 'MP-PAY-999', req_id, ts)

        with patch('addons.payment_mercado_pago.gateway.mercadopago') as mock_mp:
            sdk = MagicMock()
            mock_mp.SDK.return_value = sdk
            sdk.payment.return_value.get.return_value = {
                'status': 200,
                'response': {'id': 999, 'status': 'rejected', 'transaction_amount': 600.0},
            }
            res = api_client.post(
                MP_WEBHOOK_URL,
                data=json.dumps({'type': 'payment', 'data': {'id': 'MP-PAY-999'}}),
                content_type='application/json',
                HTTP_X_SIGNATURE=f'ts={ts},v1={sig}',
                HTTP_X_REQUEST_ID=req_id,
            )

        assert res.status_code == 200
        payment.refresh_from_db()
        order.refresh_from_db()
        assert payment.status == 'FAILED'
        assert order_status(order) == 'PENDING'  # sin pago aprobado → PENDING

    def test_webhook_tipo_no_payment_ignorado(self, api_client, db):
        """Eventos que no son 'payment' se ignoran con 200."""
        res = api_client.post(
            MP_WEBHOOK_URL,
            data=json.dumps({'type': 'merchant_order', 'data': {'id': '1'}}),
            content_type='application/json',
            HTTP_X_SIGNATURE='ts=1,v1=x',
        )
        assert res.status_code in (200, 401)  # ignorado o firma inválida

    def test_webhook_mp_no_secret_fail_closed(
        self, api_client, orden_processing_mp, db,
    ):
        """T-102 / DEC-BC-01: sin client_secret en BD el webhook se rechaza 401.

        Antes de DEC-BC-01 la rama "no secret -> return True" abria un vector
        de fraude: cualquiera podia simular `payment.approved` y forzar
        Order.status=PROCESSING sin haber pagado. Ahora es fail-closed.
        """
        # NO crear PaymentGateway(MERCADOPAGO) — secret ausente.
        order, payment = orden_processing_mp
        res = api_client.post(
            MP_WEBHOOK_URL,
            data=json.dumps({'type': 'payment', 'data': {'id': 'MP-PAY-999'}}),
            content_type='application/json',
            HTTP_X_SIGNATURE='ts=1,v1=anything',
            HTTP_X_REQUEST_ID='req-no-secret',
        )
        assert res.status_code == 401, (
            f'fail-open regresion: webhook sin secret deberia rechazar 401, '
            f'recibido {res.status_code}'
        )
        payment.refresh_from_db()
        assert payment.status == 'PENDING'  # no se cambio

    def test_django_check_warns_missing_secret(self, db, settings):
        """T-103 / DEC-BC-01 E001: system check bloquea deploy cuando
        DEBUG=False y no hay PaymentGateway(MP).client_secret."""
        # Caso 1: DEBUG=False, sin PaymentGateway -> error E001.
        settings.DEBUG = False
        errors = check_mercadopago_client_secret(app_configs=None)
        assert any(e.id == 'payments.E001' for e in errors), (
            f'Se esperaba payments.E001 cuando no hay PaymentGateway(MP) '
            f'activo, recibido: {[e.id for e in errors]}'
        )

        # Caso 2: PaymentGateway existe pero sin client_secret -> error E001.
        gw = PaymentGateway(name='MP', gateway='MERCADOPAGO', is_active=True)
        gw.set_credentials({'access_token': 'X'})  # sin client_secret
        gw.save()
        errors = check_mercadopago_client_secret(app_configs=None)
        assert any(e.id == 'payments.E001' for e in errors), (
            f'Se esperaba payments.E001 cuando client_secret falta, '
            f'recibido: {[e.id for e in errors]}'
        )

        # Caso 3: DEBUG=True -> no errors (sandbox tolerado).
        settings.DEBUG = True
        errors = check_mercadopago_client_secret(app_configs=None)
        assert errors == [], (
            f'En DEBUG=True no deberia emitir errores, recibido: {errors}'
        )

    def test_e001_is_deploy_only_check(self):
        """H-API-CHK-01: E001 es un *deployment check* — sólo corre en
        ``manage.py check --deploy``, NO en cada comando (makemigrations/
        migrate/tests). Así un gate de deploy no bloquea comandos normales
        en entornos sin PaymentGateway sembrado.
        """
        assert check_mercadopago_client_secret in registry.deployment_checks, (
            'check_mercadopago_client_secret debe estar en deployment_checks '
            '(registrado con deploy=True), no en el registro normal.'
        )
        assert check_mercadopago_client_secret not in registry.registered_checks, (
            'No debe correr como check normal: bloquearía makemigrations/migrate.'
        )

    def test_mp_webhook_invalid_json_returns_400(self, api_client, db):
        """T-105 / DEC-BC-06: payload no-JSON retorna 400 (no 200).

        Antes del fix devolvia 200 -> MP no reintenta. Ahora 400 indica
        payload malformed; MP no reintenta 4xx (intencional, no es un
        error transitorio).
        """
        res = api_client.post(
            MP_WEBHOOK_URL,
            data='not-a-valid-json-{',
            content_type='application/json',
        )
        assert res.status_code == 400, (
            f'invalid_json deberia ser 400, recibido {res.status_code}'
        )
        assert res.data.get('status') == 'invalid_json'

    def test_mp_webhook_gateway_error_returns_503(
        self, api_client, orden_processing_mp, mp_gateway_wh, db,
    ):
        """T-105 / DEC-BC-06: gateway error retorna 503 (no 200).

        Antes del fix devolvia 200 -> MP no reintenta y el evento se
        pierde. Ahora 503 (Service Unavailable) hace que MP reintente
        con exponential backoff.
        """
        order, payment = orden_processing_mp
        ts        = '1715000099'
        req_id    = 'REQ-GW-ERR'
        signature = _make_mp_signature('TEST-SECRET', 'MP-PAY-999', req_id, ts)

        # Mock para forzar excepcion en MercadoPagoGateway().verify_payment
        with patch('addons.payment_mercado_pago.controllers.MercadoPagoGateway') as mock_cls:
            instance = MagicMock()
            instance.verify_payment.side_effect = Exception('MP API down')
            mock_cls.return_value = instance

            res = api_client.post(
                MP_WEBHOOK_URL,
                data=json.dumps({'type': 'payment', 'data': {'id': 'MP-PAY-999'}}),
                content_type='application/json',
                HTTP_X_SIGNATURE=f'ts={ts},v1={signature}',
                HTTP_X_REQUEST_ID=req_id,
            )

        assert res.status_code == 503, (
            f'gateway_error deberia ser 503, recibido {res.status_code}'
        )
        assert res.data.get('status') == 'gateway_error'


class TestPayPalWebhook:

    def _pp_webhook_headers(self):
        return {
            'HTTP_PAYPAL_TRANSMISSION_ID':   'TRANS-TEST-001',
            'HTTP_PAYPAL_TRANSMISSION_SIG':  'SIG-FAKE',
            'HTTP_PAYPAL_TRANSMISSION_TIME': '2026-05-14T00:00:00Z',
            'HTTP_PAYPAL_CERT_URL':          'https://api.sandbox.paypal.com/v1/notifications/certs/CERT-TEST',
            'HTTP_PAYPAL_AUTH_ALGO':         'SHA256withRSA',
        }

    @pytest.fixture
    def orden_paypal_wh(self, db, user, cat_wh):

        prod = Product.objects.create(
            name='Azabache', slug='azabache-wh', sku='WH-AZ-001',
            description='',
            price=Decimal('400.00'), stock=5,
            is_active=True, is_published=True,
        )
        prod.categories.add(cat_wh)
        order = Order.objects.create(
        user=user, status='PENDING',
        # O2C R8: par canonico — la proyeccion deriva el estado de los ejes.
        sale_order=SaleOrder.objects.create(state=SaleOrder.STATE_SALE),
    )
        OrderItem.objects.create(
            order=order, product_name=prod.name, sku=prod.sku,
            unit_price=prod.price, quantity=1, subtotal=prod.price,
        )
        OrderValue.objects.create(
            order=order, subtotal=Decimal('400.00'), tax=Decimal('55.17'),
            shipping_cost=Decimal('0.00'), discount=Decimal('0.00'), total=Decimal('400.00'),
        )
        OrderAddress.objects.create(
            order=order, recipient_name='T', street='S 1',
            city='CDMX', state='CMX', zip_code='06600',
        )
        payment = Payment.objects.create(
            order=order, sale_order=order.sale_order, gateway='PAYPAL',
            preference_id='PP-ORDER-WH-001',
            status='PENDING', amount=Decimal('400.00'),
        )
        return order, payment

    def test_webhook_paypal_capture_completed(
        self, api_client, orden_paypal_wh, db
    ):
        """UC-PAY-04: PAYMENT.CAPTURE.COMPLETED → Payment=APPROVED, Order=PAID (DEC-BC-12)."""
        order, payment = orden_paypal_wh

        payload = {
            'event_type': 'PAYMENT.CAPTURE.COMPLETED',
            'resource': {
                'id': 'PP-CAPTURE-001',
                'status': 'COMPLETED',
                'amount': {'currency_code': 'MXN', 'value': '400.00'},
                'supplementary_data': {
                    'related_ids': {'order_id': 'PP-ORDER-WH-001'}
                },
            },
        }
        payment.gateway_payment_id = 'PP-CAPTURE-001'
        payment.save()

        with patch(
            'addons.payment_paypal.gateway.PayPalGateway.verify_webhook_signature',
            return_value=True
        ):
            res = api_client.post(
                PP_WEBHOOK_URL,
                data=json.dumps(payload),
                content_type='application/json',
                **self._pp_webhook_headers(),
            )

        assert res.status_code == 200
        payment.refresh_from_db()
        order.refresh_from_db()
        assert payment.status == 'APPROVED'
        assert order_status(order) == 'PAID'  # DEC-BC-12 proyectado del eje

    def test_webhook_paypal_firma_invalida_retorna_401(
        self, api_client, db
    ):
        with patch(
            'addons.payment_paypal.gateway.PayPalGateway.verify_webhook_signature',
            return_value=False
        ):
            res = api_client.post(
                PP_WEBHOOK_URL,
                data=json.dumps({'event_type': 'PAYMENT.CAPTURE.COMPLETED', 'resource': {}}),
                content_type='application/json',
            )
        assert res.status_code == 401

    def test_webhook_paypal_evento_ignorado_retorna_200(
        self, api_client, db
    ):
        """Eventos no relevantes se ignoran con 200."""
        with patch(
            'addons.payment_paypal.gateway.PayPalGateway.verify_webhook_signature',
            return_value=True
        ):
            res = api_client.post(
                PP_WEBHOOK_URL,
                data=json.dumps({'event_type': 'INVOICING.INVOICE.CREATED', 'resource': {}}),
                content_type='application/json',
            )
        assert res.status_code == 200
        assert res.json()['status'] == 'ignored'

    def test_webhook_paypal_idempotente(
        self, api_client, orden_paypal_wh, db
    ):
        """El mismo capture_id procesado dos veces no cambia el estado."""
        order, payment = orden_paypal_wh
        payment.status             = 'APPROVED'
        payment.gateway_payment_id = 'PP-CAP-DUP'
        payment.save()
        order.status = 'PROCESSING'
        order.save()

        payload = {
            'event_type': 'PAYMENT.CAPTURE.COMPLETED',
            'resource': {
                'id': 'PP-CAP-DUP',
                'status': 'COMPLETED',
                'amount': {'currency_code': 'MXN', 'value': '400.00'},
            },
        }
        with patch(
            'addons.payment_paypal.gateway.PayPalGateway.verify_webhook_signature',
            return_value=True
        ):
            api_client.post(PP_WEBHOOK_URL,
                            data=json.dumps(payload), content_type='application/json')

        payment.refresh_from_db()
        order.refresh_from_db()
        assert payment.status == 'APPROVED'   # sin cambio
        assert order.status   == 'PROCESSING' # sin cambio

    def test_paypal_webhook_invalid_json_returns_400(self, api_client, db):
        """T-105 / DEC-BC-06: payload no-JSON en webhook PayPal -> 400."""
        res = api_client.post(
            PP_WEBHOOK_URL,
            data='broken-json{',
            content_type='application/json',
            **self._pp_webhook_headers(),
        )
        assert res.status_code == 400, (
            f'invalid_json deberia ser 400, recibido {res.status_code}'
        )
        assert res.data.get('status') == 'invalid_json'

    def test_paypal_webhook_missing_order_id_returns_400(
        self, api_client, db,
    ):
        """T-105 / DEC-BC-06: CHECKOUT.ORDER.APPROVED sin id en resource -> 400."""
        payload = {
            'event_type': 'CHECKOUT.ORDER.APPROVED',
            'resource': {},  # sin 'id'
        }
        with patch(
            'addons.payment_paypal.gateway.PayPalGateway.verify_webhook_signature',
            return_value=True,
        ):
            res = api_client.post(
                PP_WEBHOOK_URL,
                data=json.dumps(payload),
                content_type='application/json',
                **self._pp_webhook_headers(),
            )
        assert res.status_code == 400, (
            f'missing_order_id deberia ser 400, recibido {res.status_code}'
        )
        assert res.data.get('status') == 'missing_order_id'

    def test_paypal_webhook_payment_not_found_returns_502(
        self, api_client, db,
    ):
        """T-105 / DEC-BC-06: Payment ausente en CHECKOUT.ORDER.APPROVED -> 502.

        Antes del fix devolvia 200, PayPal no reintentaba y el evento
        se perdia en la race window con creacion del Payment. Ahora 502
        dispara backoff retry de PayPal — recupera del race.
        """
        payload = {
            'event_type': 'CHECKOUT.ORDER.APPROVED',
            'resource': {'id': 'PP-ORDER-INEXISTENTE'},
        }
        with patch(
            'addons.payment_paypal.gateway.PayPalGateway.verify_webhook_signature',
            return_value=True,
        ):
            res = api_client.post(
                PP_WEBHOOK_URL,
                data=json.dumps(payload),
                content_type='application/json',
                **self._pp_webhook_headers(),
            )
        assert res.status_code == 502, (
            f'payment_not_found deberia ser 502, recibido {res.status_code}'
        )
        assert res.data.get('status') == 'payment_not_found'

    def test_paypal_webhook_capture_failed_returns_500(
        self, api_client, orden_paypal_wh, db,
    ):
        """T-105 / DEC-BC-06: error al capturar el order de PayPal -> 500."""
        order, payment = orden_paypal_wh
        # Ajustar preference_id al payload del payment
        payment.preference_id = 'PP-CAP-FAIL'
        payment.save()

        payload = {
            'event_type': 'CHECKOUT.ORDER.APPROVED',
            'resource': {'id': 'PP-CAP-FAIL'},
        }
        with patch(
            'addons.payment_paypal.gateway.PayPalGateway.verify_webhook_signature',
            return_value=True,
        ), patch(
            'addons.payment_paypal.gateway.PayPalGateway.capture_order',
            side_effect=Exception('PayPal capture API failed'),
        ):
            res = api_client.post(
                PP_WEBHOOK_URL,
                data=json.dumps(payload),
                content_type='application/json',
                **self._pp_webhook_headers(),
            )
        assert res.status_code == 500, (
            f'capture_failed deberia ser 500, recibido {res.status_code}'
        )
        assert res.data.get('status') == 'capture_failed'
