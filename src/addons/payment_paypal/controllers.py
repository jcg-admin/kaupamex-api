"""Controladores del provider PayPal — webhook UC-PAY-04.

En Odoo cada provider aloja sus endpoints en ``payment_<provider>/controllers``.
El path del webhook NO cambia (DEC-V2-02:
``/api/v1/payments/webhooks/paypal/`` registrado con el proveedor externo);
``payments/webhook_urls.py`` lo enruta hacia aquí.
"""
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
from django.db import IntegrityError, transaction

from addons.payment.models import Payment, PaymentGatewayEvent, WebhookEvent, Chargeback
from addons.payment.webhook_processing import _process_payment_approval
from addons.payment_paypal.gateway import PayPalGateway
from addons.orders.models import Order

logger = logging.getLogger('apps')

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

        # H-CICLO27-01: verificar firma ANTES del dedup.
        # El orden anterior (dedup → firma) permitía que un atacante con un
        # event_id conocido enviara un webhook falso, registrándolo en
        # WebhookEvent y marcándolo como already_processed. El webhook
        # legítimo de PayPal llegaría después y sería descartado
        # silenciosamente con 200 idempotente, bloqueando la confirmación
        # del pago. Mismo patrón que H-CICLO22-01 aplicado al webhook de MP.
        # Solución: rechazar con 401 cualquier webhook con firma inválida
        # ANTES de persistir el evento en la tabla de dedup.
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

        # DEC-BC-04: dedup via WebhookEvent solo después de validar la firma.
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
                result, newly_approved = _process_payment_approval(
                    gateway_payment_id=capture_id,
                    gateway='PAYPAL',
                    amount=amount,
                )
                # H-CICLO87-02: solo auditar si la aprobacion ocurrio ahora.
                if result and newly_approved:
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
