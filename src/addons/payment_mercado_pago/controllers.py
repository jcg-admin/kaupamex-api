"""Controladores del provider Mercado Pago — webhook UC-PAY-03.

En Odoo cada provider aloja sus endpoints en ``payment_<provider>/controllers``
(``payment_mercado_pago`` incluido). El path del webhook NO cambia
(DEC-V2-02: ``/api/v1/payments/webhooks/mercadopago/`` está registrado con el
proveedor externo); ``payments/webhook_urls.py`` lo enruta hacia aquí.

Diseño (heredado de payments/webhooks.py):
  - El endpoint retorna 200 inmediato para evitar reintentos del gateway.
  - La verificación de firma rechaza con 401 antes de procesar.
  - Idempotencia por unique(gateway_payment_id) en BD.
  - SaleOrder.status → PAID cuando pago aprobado (via webhook_processing).
"""
import json
import logging
from decimal import Decimal

from django.views.decorators.csrf import csrf_exempt
from addons.sale.models import SaleOrder
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from mercadopago.webhook import WebhookSignatureValidator, InvalidWebhookSignatureError
from django.db import IntegrityError, transaction

from addons.payment.models import Payment, PaymentGatewayEvent, WebhookEvent, Chargeback
from addons.payment.webhook_processing import _process_payment_approval
from addons.payment.models import PaymentGateway as PGModel
from addons.payment_mercado_pago.gateway import MercadoPagoGateway

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


def _verify_mp_signature(request, data_id: str) -> bool:
    """
    Verifica la firma del webhook de MercadoPago con el validador oficial del
    SDK (``mercadopago.webhook.WebhookSignatureValidator``). FR-PAY-03.01.

    El validador arma el manifest ``id:{data.id};request-id:{x-request-id};ts:{ts}``
    con las reglas correctas de MP: toma el ``data.id`` del **query param**, lo
    pasa a minúsculas, y **omite** los segmentos ausentes antes del HMAC
    (F-WH-01/02/03). Comparación en tiempo constante (anti-timing).

    ``data_id``: se toma del query param ``data.id`` (spec de MP); si no viene en
    el query, se usa el valor recibido (body) como respaldo.

    NOTA (F-WH-07): NO se pasa ``tolerance_seconds`` a propósito — MP reintenta
    la entrega cada 15 min reusando el ``ts`` original, así que una tolerancia
    corta rechazaría reintentos legítimos. El replay lo neutralizan el dedup
    (``WebhookEvent``) y ``verify_payment``.
    """
    x_signature  = request.META.get('HTTP_X_SIGNATURE')
    x_request_id = request.META.get('HTTP_X_REQUEST_ID')
    data_id_q    = request.GET.get('data.id') or data_id

    secret = _get_mp_client_secret()
    if not secret:
        # DEC-BC-01 (2026-05-21): fail-closed. Sin secret, rechazar todo webhook
        # (la rama histórica "return True" abría fraude). El system check
        # payments.E001 bloquea el deploy si DEBUG=False y falta el secret.
        logger.error('MP webhook: client_secret no configurado — rechazando webhook')
        return False

    try:
        WebhookSignatureValidator.validate(x_signature, x_request_id, data_id_q, secret)
        return True
    except InvalidWebhookSignatureError:
        return False



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

        # Solo procesar notificaciones de tipo 'payment' o 'chargebacks'
        event_type   = data.get('type', '')
        resource_id  = str(data.get('data', {}).get('id', ''))
        request_id   = request.META.get('HTTP_X_REQUEST_ID', '')

        if event_type == 'chargebacks' and resource_id:
            # F-WH-08: verificar la firma también en contracargos ANTES de
            # procesar (antes se procesaba sin autenticar → webhook forjable).
            if not _verify_mp_signature(request, resource_id):
                logger.warning('MP webhook: firma inválida para chargeback=%s', resource_id)
                return Response({'status': 'invalid_signature'}, status=401)
            return self._handle_chargeback(data, resource_id)

        # T-302: MP notifica los cobros migrados a Orders con ``type: order``
        # y ``data.id`` = ``ORD...``; los legacy siguen llegando como
        # ``type: payment`` con ``data.id`` = payment id. Ambos se procesan por
        # el mismo camino; solo cambia la consulta al gateway (verify_order vs
        # verify_payment) y el lookup del Payment (mp_order_id vs
        # gateway_payment_id).
        is_order   = event_type == 'order'
        payment_id = resource_id
        if event_type not in ('payment', 'order') or not payment_id:
            return Response({'status': 'ignored', 'type': event_type}, status=200)

        # H-CICLO22-01: verificar firma ANTES del dedup.
        # El orden anterior (dedup → firma) permitía que un atacante con un
        # payment_id conocido enviara un webhook falso, registrándolo en
        # WebhookEvent y marcándolo como already_processed. El webhook
        # legítimo de MP llegaría después y sería descartado silenciosamente
        # con 200 idempotente, bloqueando la confirmación del pago.
        # Solución: rechazar con 401 cualquier webhook con firma inválida
        # ANTES de persistir el evento en la tabla de dedup.
        if not _verify_mp_signature(request, payment_id):
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

        # Consultar estado definitivo al gateway (paso 6 del flujo).
        # ``order`` → verify_order(ORD) devuelve el PAY anidado; ``payment`` →
        # verify_payment(payment_id) legacy.
        try:
            gw = MercadoPagoGateway()
            gw_result = gw.verify_order(payment_id) if is_order else gw.verify_payment(payment_id)
        except Exception as exc:
            # DEC-BC-06: 503 (Service Unavailable) indica gateway externo
            # caido. MP hace exponential backoff en 5xx y reintenta el
            # webhook — el evento no se pierde.
            logger.error('MP webhook: error consultando estado: %s', exc)
            return Response({'status': 'gateway_error'}, status=503)

        # Para orders, el ``data.id`` es la ORD; el PAY (para matchear el
        # Payment y procesar la aprobación) sale de la consulta a Orders.
        pay_gpi = (gw_result.gateway_payment_id or payment_id) if is_order else payment_id

        # Registrar evento de auditoría
        payment = (
            Payment.objects
            .filter(preference_id__isnull=False, gateway='MERCADOPAGO')
            .filter(order__order_number=data.get('external_reference', ''))
            .first()
        )
        # Si no encontramos por order_number: en orders buscamos por mp_order_id
        # (ORD), en legacy por gateway_payment_id (payment id).
        if not payment and is_order:
            payment = Payment.objects.filter(
                mp_order_id=payment_id, gateway='MERCADOPAGO'
            ).first()
        if not payment:
            payment = Payment.objects.filter(
                gateway_payment_id=pay_gpi, gateway='MERCADOPAGO'
            ).first()

        if payment:
            PaymentGatewayEvent.objects.create(
                payment=payment,
                event_type=PaymentGatewayEvent.EVENT_WEBHOOK_RECEIVED,
                raw_body=raw_body,
            )

        # Actualizar gateway_payment_id / mp_order_id si aún no los tiene
        if payment:
            update_fields = []
            if not payment.gateway_payment_id and pay_gpi:
                payment.gateway_payment_id = pay_gpi
                update_fields.append('gateway_payment_id')
            if is_order and not payment.mp_order_id:
                payment.mp_order_id = payment_id
                update_fields.append('mp_order_id')
            if update_fields:
                update_fields.append('updated_at')
                payment.save(update_fields=update_fields)

        # Procesar según el estado
        if gw_result.status == 'approved':
            result, newly_approved = _process_payment_approval(
                gateway_payment_id=pay_gpi,
                gateway='MERCADOPAGO',
                amount=gw_result.amount,
            )
            # H-CICLO87-02: solo crear EVENT_PAYMENT_APPROVED cuando la
            # transicion ocurrio en esta llamada (newly_approved=True).
            # En llamadas idempotentes (pago ya APPROVED) no se duplica
            # el registro de auditoria.
            if payment and result and newly_approved:
                PaymentGatewayEvent.objects.create(
                    payment=result,
                    event_type=PaymentGatewayEvent.EVENT_PAYMENT_APPROVED,
                    raw_body=json.dumps({'gateway_payment_id': payment_id}),
                )
        elif gw_result.status in ('rejected', 'cancelled'):
            # 'cancelled' ocurre cuando el voucher de un método no-tarjeta
            # (OXXO, Paycash, cajero, SPEI) vence sin haber sido pagado.
            # Tratamos como FAILED para que la orden quede disponible para retry.
            if payment:
                with transaction.atomic():
                    payment.status = Payment.STATUS_FAILED
                    payment.save(update_fields=['status', 'updated_at'])
                    PaymentGatewayEvent.objects.create(
                        payment=payment,
                        event_type=PaymentGatewayEvent.EVENT_PAYMENT_FAILED,
                        raw_body=json.dumps({
                            'gateway_payment_id': payment_id,
                            'mp_status': gw_result.status,
                        }),
                    )

        return Response({'status': 'processed'}, status=200)

    def _handle_chargeback(self, data: dict, chargeback_id: str):
        """
        Procesa un webhook de contracargo de MercadoPago. T-17-A.
        Crea o actualiza el registro Chargeback en DB.
        Siempre retorna 200 para que MP no reintente.
        """
        gateway_payment_id = str(data.get('payment_id', ''))
        try:
            cb_data = MercadoPagoGateway().get_chargeback(chargeback_id)
            cb_resp = cb_data.get('response', {})
        except Exception as exc:
            logger.error('MP chargeback webhook: error consultando chargeback %s: %s', chargeback_id, exc)
            return Response({'status': 'gateway_error'}, status=200)

        payment = Payment.objects.filter(
            gateway_payment_id=gateway_payment_id, gateway='MERCADOPAGO',
        ).first()

        status_map = {
            'pending':   Chargeback.STATUS_PENDING,
            'lost':      Chargeback.STATUS_LOST,
            'won':       Chargeback.STATUS_WON,
            'cancelled': Chargeback.STATUS_CANCELLED,
            'closed':    Chargeback.STATUS_CLOSED,
        }
        mp_status    = cb_resp.get('status', 'pending')
        cb_status    = status_map.get(mp_status, Chargeback.STATUS_PENDING)
        amount       = cb_resp.get('amount', 0)
        reason_code  = cb_resp.get('reason_code', '')
        description  = cb_resp.get('description', '')
        gw_payment   = str(cb_resp.get('payment_id', gateway_payment_id))

        with transaction.atomic():
            cb, created = Chargeback.objects.get_or_create(
                gateway_chargeback_id=chargeback_id,
                defaults={
                    'payment':            payment,
                    'gateway_payment_id': gw_payment,
                    'amount':             amount,
                    'status':             cb_status,
                    'reason_code':        reason_code,
                    'description':        description,
                },
            )
            if not created:
                cb.status      = cb_status
                cb.description = description
                cb.save(update_fields=['status', 'description', 'updated_at'])

        action = 'created' if created else 'updated'
        logger.info('MP chargeback webhook: %s chargeback_id=%s status=%s', action, chargeback_id, cb_status)
        return Response({'status': 'processed', 'chargeback': action}, status=200)

