"""
Webhook handlers — addons.delivery (LOG-04 / US-1.2 / DEC-LOOP-05).

Courier status webhook. The courier's tracking platform calls this endpoint
to push shipment status changes; the manual admin PATCH (LOG-02) remains as a
fallback and is untouched.

Design (mirrors addons.payments.webhooks):
  - AllowAny: no JWT. Authenticated by an HMAC-SHA256 signature with a shared
    per-courier secret (Courier.webhook_secret, Fernet-encrypted).
  - Verify signature BEFORE processing; reject with 401 on bad/missing
    signature or missing secret (fail-closed).
  - Idempotent: replaying the same event (same guide+status+occurred_at) does
    not duplicate the ShipmentEvent and still returns 200.
"""
import json
import logging
from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiResponse
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from config.schema import error_response
from .models import Courier, ShipmentEvent, ShipmentGuide

logger = logging.getLogger('apps')


# Mapa explícito: estado del courier (canónico del payload, lowercase) →
# ShipmentGuide.STATUS_*. Estados de courier fuera de este mapa → 400.
# DEC-LOOP-05: los couriers reportan vocabulario propio; el webhook lo
# normaliza al estado interno de la guía.
COURIER_STATUS_MAP = {
    'picked_up':  ShipmentGuide.STATUS_PICKED_UP,
    'in_transit': ShipmentGuide.STATUS_IN_TRANSIT,
    'delivered':  ShipmentGuide.STATUS_DELIVERED,
    'incident':   ShipmentGuide.STATUS_INCIDENT,
    'cancelled':  ShipmentGuide.STATUS_CANCELLED,
}


@method_decorator(csrf_exempt, name='dispatch')
class CourierWebhookView(APIView):
    """
    POST /api/v1/logistics/webhook/courier/

    Recibe notificaciones de estado de un courier (LOG-04, US-1.2).

    Auth: firma HMAC-SHA256 con el secreto compartido del courier
    (sin JWT). Header ``X-Signature`` = HMAC-SHA256(courier.webhook_secret,
    raw_body) en hex.

    Payload (JSON)::

        {
          "courier_code":    "ESF",          # Courier.code (requerido)
          "tracking_number": "TRK-0001",      # guía a actualizar (requerido)
          "status":          "in_transit",    # estado del courier (requerido)
          "occurred_at":     "2026-06-03T18:00:00Z",  # ISO 8601 (requerido)
          "note":            "En ruta"        # opcional
        }

    ``status`` del courier se mapea a ShipmentGuide.STATUS_* vía
    COURIER_STATUS_MAP; estados desconocidos → 400 STATUS_INVALID.

    Idempotente: un reenvío del mismo evento (misma guía + status +
    occurred_at) no duplica el ShipmentEvent y responde 200.
    """
    permission_classes = [AllowAny]
    serializer_class = serializers.Serializer

    @extend_schema(
        summary='Webhook de estado de courier (LOG-04)',
        description=(
            'Recibe cambios de estado de envío desde la plataforma del '
            'courier. Verifica la firma HMAC-SHA256 (header X-Signature) con '
            'el secreto compartido del courier antes de procesar. Idempotente: '
            'reenviar el mismo evento no duplica el historial. El PATCH admin '
            'manual (LOG-02) sigue disponible como fallback.'
        ),
        tags=['logistics'],
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    'CourierWebhookResponse',
                    {'status': serializers.CharField(),
                     'guide_status': serializers.CharField(required=False)}),
                description='Evento recibido / procesado.'),
            400: error_response('Payload inválido o estado desconocido'),
            401: error_response('Firma inválida o ausente'),
            404: error_response('Courier o guía no encontrada'),
        },
    )
    def post(self, request):
        raw_body = request.body

        try:
            data = json.loads(raw_body.decode('utf-8', errors='replace'))
        except json.JSONDecodeError:
            return Response(
                {'detail': 'Payload no es JSON válido.', 'codigo_error': 'INVALID_PAYLOAD'},
                status=400,
            )
        if not isinstance(data, dict):
            return Response(
                {'detail': 'Payload no es un objeto JSON.', 'codigo_error': 'INVALID_PAYLOAD'},
                status=400,
            )

        courier_code    = (data.get('courier_code') or '').strip()
        tracking_number = (data.get('tracking_number') or '').strip()
        courier_status  = (data.get('status') or '').strip().lower()
        occurred_at_raw = (data.get('occurred_at') or '').strip()
        note            = (data.get('note') or '').strip()

        # Campos requeridos del payload (400 antes de cualquier lookup).
        if not courier_code or not tracking_number or not courier_status or not occurred_at_raw:
            return Response(
                {
                    'detail': 'Campos requeridos: courier_code, tracking_number, status, occurred_at.',
                    'codigo_error': 'INVALID_PAYLOAD',
                },
                status=400,
            )

        # Localizar el courier para verificar la firma. Si no existe, no hay
        # secreto contra el cual verificar → 401 fail-closed (no se revela si
        # el courier existe; tampoco se procesa nada sin firma válida).
        signature = request.META.get('HTTP_X_SIGNATURE', '')
        courier = Courier.objects.filter(code=courier_code).first()
        if courier is None or not courier.verify_webhook_signature(raw_body, signature):
            logger.warning(
                'Courier webhook: firma inválida o courier desconocido code=%s',
                courier_code,
            )
            return Response(
                {'detail': 'Firma inválida.', 'codigo_error': 'INVALID_SIGNATURE'},
                status=401,
            )

        # Firma válida: a partir de aquí podemos revelar 404 (la firma prueba
        # que el emisor conoce el secreto del courier).
        occurred_at = parse_datetime(occurred_at_raw)
        if occurred_at is None:
            return Response(
                {'detail': 'occurred_at no es una fecha ISO 8601 válida.', 'codigo_error': 'INVALID_PAYLOAD'},
                status=400,
            )

        new_status = COURIER_STATUS_MAP.get(courier_status)
        if new_status is None:
            return Response(
                {
                    'detail': (
                        f'Estado de courier desconocido: {courier_status!r}. '
                        f'Valores: {sorted(COURIER_STATUS_MAP)}.'
                    ),
                    'codigo_error': 'STATUS_INVALID',
                },
                status=400,
            )

        guide = ShipmentGuide.objects.filter(
            courier=courier, tracking_number=tracking_number, is_deleted=False,
        ).select_related('order').first()
        if guide is None:
            return Response(
                {'detail': 'Guía no encontrada.', 'codigo_error': 'SHIPMENT_GUIDE_NOT_FOUND'},
                status=404,
            )

        # Idempotencia: un reenvío del mismo evento (misma guía + status +
        # occurred_at) no duplica el ShipmentEvent y responde 200.
        if ShipmentEvent.objects.filter(
            guide=guide, status=new_status, occurred_at=occurred_at,
        ).exists():
            logger.info(
                'Courier webhook: evento duplicado guide=%s status=%s — 200 idempotente',
                guide.pk, new_status,
            )
            return Response({'status': 'already_processed', 'guide_status': guide.status}, status=200)

        # Transacción atómica: update de la guía + create del evento append-only.
        # recorded_by=None: lo registró el sistema del courier, no un admin.
        with transaction.atomic():
            guide_locked = ShipmentGuide.objects.select_for_update().get(pk=guide.pk)
            # Re-check idempotente dentro del lock (dos reenvíos concurrentes).
            if ShipmentEvent.objects.filter(
                guide=guide_locked, status=new_status, occurred_at=occurred_at,
            ).exists():
                return Response(
                    {'status': 'already_processed', 'guide_status': guide_locked.status},
                    status=200,
                )
            guide_locked.status = new_status
            guide_locked.save(update_fields=['status', 'updated_at'])
            ShipmentEvent.objects.create(
                guide=guide_locked, status=new_status,
                description=note, occurred_at=occurred_at, recorded_by=None,
            )

        return Response({'status': 'processed', 'guide_status': new_status}, status=200)
