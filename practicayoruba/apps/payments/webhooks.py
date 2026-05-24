"""
Webhook handlers — apps.payments

UC-PAY-03: MercadoPago webhook
UC-PAY-04: PayPal webhook

Diseño:
  - Los endpoints retornan 200 inmediatamente (paso 4 del flujo)
    para evitar que el gateway reintente la entrega.
  - La verificación de firma rechaza con 401 antes de procesar.
  - La idempotencia está garantizada por unique(gateway_payment_id) en BD.
  - Order.status → PROCESSING cuando pago aprobado (H-PAY-002).
"""
import hashlib
import hmac
import json
import logging
from decimal import Decimal
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import IntegrityError
from .models import Payment, PaymentGatewayEvent, WebhookEvent
from apps.settings_app.models import PaymentGateway as PGModel
from django.db import transaction
from .gateways.mercadopago import MercadoPagoGateway
from .gateways.paypal import PayPalGateway
from apps.orders.models import Order



logger = logging.getLogger('apps')


def _get_mp_client_secret() -> str | None:
    """Lee el client_secret de MercadoPago para verificar firmas de webhooks."""
    try:
        gw    = PGModel.objects.get(gateway='MERCADOPAGO', is_active=True)
        creds = gw.get_credentials()
        return creds.get('client_secret')
    except Exception:
        # Loud-log: si no podemos leer el secret, todos los webhooks
        # MP seran rechazados con 401. Operaciones debe verlo. DEC-DOC-008.
        logger.error(
            'MP webhook: cannot read client_secret', exc_info=True,
        )
        return None


def _verify_mp_signature(request, payment_id: str, request_id: str) -> bool:
    """
    Verifica la firma HMAC-SHA256 de un webhook de MercadoPago.
    FR-PAY-03.01 (H-PAY-004).
    Algoritmo: HMAC-SHA256(client_secret, 'id:{pid};request-id:{rid};ts:{ts}')
    """
    signature_header = request.META.get('HTTP_X_SIGNATURE', '')
    if not signature_header:
        return False

    # Parsear ts y v1 del header: "ts=1234;v1=abcdef..."
    parts = dict(p.split('=', 1) for p in signature_header.split(';') if '=' in p)
    ts = parts.get('ts', '')
    v1 = parts.get('v1', '')
    if not ts or not v1:
        return False

    client_secret = _get_mp_client_secret()
    if not client_secret:
        # DEC-BC-01 (2026-05-21): fail-closed por seguridad. La rama
        # historica "return True" abria un vector de fraude (cualquiera
        # podia simular `payment.approved`). El system check en apps.py
        # bloquea el deploy si DEBUG=False y no hay client_secret.
        logger.error('MP webhook: client_secret no configurado — rechazando webhook')
        return False

    manifest = f'id:{payment_id};request-id:{request_id};ts:{ts}'
    expected = hmac.new(
        client_secret.encode(),
        manifest.encode(),
        hashlib.sha256,
    ).hexdigest()

    # Comparación en tiempo constante para prevenir timing attacks
    return hmac.compare_digest(expected, v1)


def _process_payment_approval(gateway_payment_id: str, gateway: str, amount: Decimal | None = None) -> Payment | None:
    """
    Actualiza Payment y Order cuando el pago es aprobado.
    Idempotente: si el Payment ya es APPROVED, no cambia nada.
    FR-PAY-03.02, FR-PAY-04.01 (H-PAY-005).
    """

    with transaction.atomic():
        payment = (
            Payment.objects
            .select_for_update()
            .select_related('order')
            .filter(gateway_payment_id=gateway_payment_id, gateway=gateway)
            .first()
        )
        if not payment:
            logger.warning(
                'Webhook %s: no se encontró Payment con gateway_payment_id=%s',
                gateway, gateway_payment_id,
            )
            return None

        if payment.status == Payment.STATUS_APPROVED:
            logger.info('Webhook %s: pago %s ya estaba APPROVED — idempotente', gateway, gateway_payment_id)
            return payment

        payment.status = Payment.STATUS_APPROVED
        if amount:
            payment.amount = amount
        payment.save(update_fields=['status', 'amount', 'updated_at'])

        # DEC-BC-12: Order → PAGADA cuando pago aprobado (confirma pago recibido).
        order = payment.order
        if order.status in (Order.STATUS_PENDING, Order.STATUS_PROCESSING):
            order.status = Order.STATUS_PAGADA
            order.save(update_fields=['status', 'updated_at'])
            logger.info(
                'Orden %s → PAGADA tras pago aprobado (%s)',
                order.order_number, gateway,
            )

    return payment


# =============================================================================
# UC-PAY-03 — Webhook de MercadoPago
# =============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class MercadoPagoWebhookView(APIView):
    """
    POST /api/v1/payments/webhooks/mercadopago/
    Recibe notificaciones de estado de pago de MercadoPago.
    UC-PAY-03 (FR-PAY-03.01, FR-PAY-03.02).

    Seguridad:
      - Verificación HMAC-SHA256 antes de procesar (FR-PAY-03.01).
      - Siempre responde 200 para que MP no reintente (paso 4 del flujo).
      - Procesamiento idempotente por gateway_payment_id.
    """
    permission_classes = [AllowAny]
    serializer_class = serializers.Serializer

    @extend_schema(
        summary='Webhook de MercadoPago',
        description=(
            'Recibe notificaciones de pago de MercadoPago. '
            'Verifica la firma HMAC-SHA256 antes de procesar. '
            'Idempotente: el mismo evento procesado dos veces no cambia el estado. '
            'Siempre retorna 200 para que MP no reintente la entrega.'
        ),
        responses={200: OpenApiResponse(description='Evento recibido.')},
        tags=['payments-webhooks'],
    )
    def post(self, request):
        raw_body = request.body.decode('utf-8', errors='replace')

        # Parsear payload
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError:
            # DEC-BC-06: 400 indica al cliente que el payload es invalido.
            # MP no reintenta 4xx — el evento se descarta como malformed.
            logger.warning('MP webhook: payload no es JSON válido')
            return Response({'status': 'invalid_json'}, status=400)

        # Solo procesar notificaciones de tipo 'payment'
        event_type   = data.get('type', '')
        payment_id   = str(data.get('data', {}).get('id', ''))
        request_id   = request.META.get('HTTP_X_REQUEST_ID', '')

        if event_type != 'payment' or not payment_id:
            return Response({'status': 'ignored', 'type': event_type}, status=200)

        # H-CICLO22-01: verificar firma ANTES del dedup.
        # El orden anterior (dedup → firma) permitía que un atacante con un
        # payment_id conocido enviara un webhook falso, registrándolo en
        # WebhookEvent y marcándolo como already_processed. El webhook
        # legítimo de MP llegaría después y sería descartado silenciosamente
        # con 200 idempotente, bloqueando la confirmación del pago.
        # Solución: rechazar con 401 cualquier webhook con firma inválida
        # ANTES de persistir el evento en la tabla de dedup.
        if not _verify_mp_signature(request, payment_id, request_id):
            logger.warning('MP webhook: firma inválida para payment_id=%s', payment_id)
            return Response({'status': 'invalid_signature'}, status=401)

        # DEC-BC-04: dedup via WebhookEvent solo después de validar la firma.
        # transaction.atomic() crea un savepoint: el IntegrityError solo
        # revierte el savepoint, no la transacción de test ni la de la vista.
        try:
            with transaction.atomic():
                WebhookEvent.objects.create(
                    gateway='MERCADOPAGO',
                    event_id=payment_id,
                    transmission_id=request_id,
                    raw_body=raw_body,
                )
        except IntegrityError:
            logger.info('MP webhook: evento duplicado payment_id=%s — 200 idempotente', payment_id)
            return Response({'status': 'already_processed'}, status=200)

        # Consultar estado definitivo al gateway (paso 6 del flujo)
        try:
            gw_result = MercadoPagoGateway().verify_payment(payment_id)
        except Exception as exc:
            # DEC-BC-06: 503 (Service Unavailable) indica gateway externo
            # caido. MP hace exponential backoff en 5xx y reintenta el
            # webhook — el evento no se pierde.
            logger.error('MP webhook: error consultando estado: %s', exc)
            return Response({'status': 'gateway_error'}, status=503)

        # Registrar evento de auditoría
        payment = (
            Payment.objects
            .filter(preference_id__isnull=False, gateway='MERCADOPAGO')
            .filter(order__order_number=data.get('external_reference', ''))
            .first()
        )
        # Si no encontramos por order_number, buscar por gateway_payment_id
        if not payment:
            payment = Payment.objects.filter(
                gateway_payment_id=payment_id, gateway='MERCADOPAGO'
            ).first()

        if payment:
            PaymentGatewayEvent.objects.create(
                payment=payment,
                event_type=PaymentGatewayEvent.EVENT_WEBHOOK_RECEIVED,
                raw_body=raw_body,
            )

        # Actualizar gateway_payment_id si aún no lo tiene
        if payment and not payment.gateway_payment_id:
            payment.gateway_payment_id = payment_id
            payment.save(update_fields=['gateway_payment_id', 'updated_at'])

        # Procesar según el estado
        if gw_result.status == 'approved':
            result = _process_payment_approval(
                gateway_payment_id=payment_id,
                gateway='MERCADOPAGO',
                amount=gw_result.amount,
            )
            if payment and result:
                PaymentGatewayEvent.objects.create(
                    payment=result,
                    event_type=PaymentGatewayEvent.EVENT_PAYMENT_APPROVED,
                    raw_body=json.dumps({'gateway_payment_id': payment_id}),
                )
        elif gw_result.status == 'rejected':
            if payment:
                with transaction.atomic():
                    payment.status = Payment.STATUS_FAILED
                    payment.save(update_fields=['status', 'updated_at'])
                    PaymentGatewayEvent.objects.create(
                        payment=payment,
                        event_type=PaymentGatewayEvent.EVENT_PAYMENT_FAILED,
                        raw_body=json.dumps({'gateway_payment_id': payment_id}),
                    )

        return Response({'status': 'processed'}, status=200)


# =============================================================================
# UC-PAY-04 — Webhook de PayPal
# =============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class PayPalWebhookView(APIView):
    """
    POST /api/v1/payments/webhooks/paypal/
    Recibe notificaciones de PayPal (IPN/Webhooks).
    UC-PAY-04 (FR-PAY-04.01).

    Eventos procesados:
      - CHECKOUT.ORDER.APPROVED → captura el pago
      - PAYMENT.CAPTURE.COMPLETED → marca como aprobado
      - PAYMENT.CAPTURE.DENIED → marca como fallido
    """
    permission_classes = [AllowAny]
    serializer_class = serializers.Serializer

    @extend_schema(
        summary='Webhook de PayPal',
        description=(
            'Recibe notificaciones de PayPal. '
            'Verifica la firma consultando la API de PayPal (FR-PAY-04.01). '
            'Procesa CHECKOUT.ORDER.APPROVED y PAYMENT.CAPTURE.COMPLETED. '
            'Idempotente. Retorna 200 siempre para evitar reintentos.'
        ),
        responses={200: OpenApiResponse(description='Evento recibido.')},
        tags=['payments-webhooks'],
    )
    def post(self, request):
        raw_body = request.body.decode('utf-8', errors='replace')

        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError:
            # DEC-BC-06: 400 — PayPal no reintenta 4xx.
            return Response({'status': 'invalid_json'}, status=400)

        event_type      = data.get('event_type', '')
        paypal_event_id = data.get('id', '')
        transmission_id = request.META.get('HTTP_PAYPAL_TRANSMISSION_ID', '')

        # DEC-BC-04: dedup via WebhookEvent antes de verificar firma.
        # transaction.atomic() crea savepoint para aislar el IntegrityError.
        if paypal_event_id:
            try:
                with transaction.atomic():
                    WebhookEvent.objects.create(
                        gateway='PAYPAL',
                        event_id=paypal_event_id,
                        transmission_id=transmission_id,
                        raw_body=raw_body,
                    )
            except IntegrityError:
                logger.info(
                    'PayPal webhook: evento duplicado id=%s — 200 idempotente',
                    paypal_event_id,
                )
                return Response({'status': 'already_processed'}, status=200)

        # Verificar firma consultando PayPal (H-PAY-003)
        try:
            pp_gateway = PayPalGateway()
            headers = {
                'paypal-cert-url':        request.META.get('HTTP_PAYPAL_CERT_URL', ''),
                'paypal-auth-algo':       request.META.get('HTTP_PAYPAL_AUTH_ALGO', ''),
                'paypal-transmission-id': request.META.get('HTTP_PAYPAL_TRANSMISSION_ID', ''),
                'paypal-transmission-sig':request.META.get('HTTP_PAYPAL_TRANSMISSION_SIG', ''),
                'paypal-transmission-time':request.META.get('HTTP_PAYPAL_TRANSMISSION_TIME',''),
            }
            is_valid = pp_gateway.verify_webhook_signature(
                webhook_id='',
                headers=headers,
                raw_body=raw_body,
            )
        except Exception as exc:
            logger.warning('PayPal webhook: error verificando firma: %s', exc)
            is_valid = False

        if not is_valid:
            logger.warning('PayPal webhook: firma inválida para event_type=%s', event_type)
            return Response({'status': 'invalid_signature'}, status=401)

        # Ignorar eventos no relevantes (responder 200 de todas formas)
        relevant = {
            'CHECKOUT.ORDER.APPROVED',
            'PAYMENT.CAPTURE.COMPLETED',
            'PAYMENT.CAPTURE.DENIED',
        }
        if event_type not in relevant:
            return Response({'status': 'ignored', 'event_type': event_type}, status=200)

        # Extraer identificadores del payload
        resource = data.get('resource', {})

        if event_type == 'CHECKOUT.ORDER.APPROVED':
            # Capturar el pago (H-PAY-006: la captura ocurre en el webhook)
            paypal_order_id = resource.get('id', '')
            if not paypal_order_id:
                # DEC-BC-06: 400 — payload incompleto, no reintentable.
                return Response({'status': 'missing_order_id'}, status=400)

            # Buscar el Payment por preference_id (guardamos el order_id de PayPal ahí)
            payment = Payment.objects.filter(
                preference_id=paypal_order_id,
                gateway='PAYPAL',
            ).first()
            if not payment:
                # DEC-BC-06: 502 (Bad Gateway) — el Payment puede aparecer
                # en una race window con la creacion del pedido. PayPal
                # hace backoff en 5xx y reintenta — recupera del race.
                logger.warning('PayPal webhook: Payment no encontrado para order=%s', paypal_order_id)
                return Response({'status': 'payment_not_found'}, status=502)

            PaymentGatewayEvent.objects.create(
                payment=payment,
                event_type=PaymentGatewayEvent.EVENT_WEBHOOK_RECEIVED,
                raw_body=raw_body,
            )

            try:
                capture_result = pp_gateway.capture_order(paypal_order_id)
                capture_id     = capture_result['capture_id']
                payment.gateway_payment_id = capture_id
                payment.save(update_fields=['gateway_payment_id', 'updated_at'])
            except Exception as exc:
                # DEC-BC-06: 500 — fallo interno al capturar. PayPal
                # hace backoff en 5xx y reintenta el webhook.
                logger.error('PayPal capture failed: %s', exc)
                return Response({'status': 'capture_failed'}, status=500)

        elif event_type == 'PAYMENT.CAPTURE.COMPLETED':
            capture_id = resource.get('id', '')
            amount_str = resource.get('amount', {}).get('value')
            amount     = Decimal(amount_str) if amount_str else None

            payment = Payment.objects.filter(
                gateway_payment_id=capture_id,
                gateway='PAYPAL',
            ).first()
            if not payment:
                # Buscar por order reference
                reference = data.get('resource', {}).get('supplementary_data', {}).get(
                    'related_ids', {}).get('order_id', '')
                if reference:
                    payment = Payment.objects.filter(
                        preference_id=reference, gateway='PAYPAL'
                    ).first()
                    if payment:
                        payment.gateway_payment_id = capture_id
                        payment.save(update_fields=['gateway_payment_id', 'updated_at'])

            if payment:
                PaymentGatewayEvent.objects.create(
                    payment=payment,
                    event_type=PaymentGatewayEvent.EVENT_WEBHOOK_RECEIVED,
                    raw_body=raw_body,
                )
                result = _process_payment_approval(
                    gateway_payment_id=capture_id,
                    gateway='PAYPAL',
                    amount=amount,
                )
                if result:
                    PaymentGatewayEvent.objects.create(
                        payment=result,
                        event_type=PaymentGatewayEvent.EVENT_PAYMENT_APPROVED,
                        raw_body=json.dumps({'capture_id': capture_id}),
                    )

        elif event_type == 'PAYMENT.CAPTURE.DENIED':
            capture_id = resource.get('id', '')
            payment = Payment.objects.filter(
                gateway_payment_id=capture_id, gateway='PAYPAL'
            ).first()
            if payment:
                with transaction.atomic():
                    payment.status = Payment.STATUS_FAILED
                    payment.save(update_fields=['status', 'updated_at'])
                    PaymentGatewayEvent.objects.create(
                        payment=payment,
                        event_type=PaymentGatewayEvent.EVENT_PAYMENT_FAILED,
                        raw_body=raw_body,
                    )

        return Response({'status': 'processed', 'event_type': event_type}, status=200)
