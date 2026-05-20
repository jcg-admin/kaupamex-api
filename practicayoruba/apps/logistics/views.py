"""
Views — apps.logistics (P-13 / UC-LOG-01..09).

Endpoints (all admin-only — RNF-SEC-003):
  GET    /api/v1/logistics/                           Panel (groups A + B).
  GET    /api/v1/logistics/couriers/                  List active couriers.
  POST   /api/v1/logistics/guides/                    Create shipment guide.
  PATCH  /api/v1/logistics/guides/<pk>/               Update status.
  POST   /api/v1/logistics/guides/<pk>/confirm-delivery/ Idempotent.

English identifiers + JSON keys (DEC-DOC-005).
Spanish business error codes (DEC-DOC-006).
"""
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order

from .models import Courier, ShipmentEvent, ShipmentGuide
from .serializers import (
    CourierSerializer,
    ShipmentEventSerializer,
    ShipmentGuideCreateSerializer,
    ShipmentGuideSerializer,
)


class _AdminOnly:
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = ShipmentGuideSerializer


# =============================================================================
# GET /api/v1/logistics/  — panel
# =============================================================================

class LogisticsPanelView(_AdminOnly, APIView):
    @extend_schema(
        summary='Logistics panel (group A + B).',
        parameters=[OpenApiParameter('courier_id', int, required=False)],
        tags=['logistics'],
    )
    def get(self, request):
        courier_id = request.query_params.get('courier_id')

        # Group A: paid orders WITHOUT shipment guide.
        paid_statuses = [
            Order.STATUS_PROCESSING,
            Order.STATUS_IN_PREPARATION,
        ]
        # The "paid" criterion: orders past PENDING that don't have a guide.
        group_a_qs = (
            Order.objects.filter(status__in=paid_statuses)
            .exclude(shipment_guide__isnull=False)
            .order_by('-created_at')
        )

        # Group B: active guides (not DELIVERED / CANCELLED).
        active_statuses = [
            ShipmentGuide.STATUS_CREATED,
            ShipmentGuide.STATUS_PICKED_UP,
            ShipmentGuide.STATUS_IN_TRANSIT,
            ShipmentGuide.STATUS_INCIDENT,
        ]
        group_b_qs = (
            ShipmentGuide.objects.filter(status__in=active_statuses)
            .select_related('order', 'courier')
            .prefetch_related('events')
            .order_by('-created_at')
        )
        if courier_id:
            try:
                cid = int(courier_id)
            except (TypeError, ValueError):
                raise ValidationError({
                    'detail': 'courier_id invalido.',
                    'codigo_error': 'COURIER_ID_INVALIDO',
                })
            group_b_qs = group_b_qs.filter(courier_id=cid)

        group_a = [
            {
                'order_id': o.id,
                'order_number': o.order_number,
                'status': o.status,
                'created_at': o.created_at,
            }
            for o in group_a_qs
        ]
        group_b = ShipmentGuideSerializer(group_b_qs, many=True).data

        return Response({
            'pending_pickup':  group_a,   # group A — UI label
            'in_transit':      group_b,   # group B — UI label
            'group_a_count':   len(group_a),
            'group_b_count':   len(group_b),
        })


# =============================================================================
# GET /api/v1/logistics/couriers/
# =============================================================================

class CourierListView(_AdminOnly, APIView):
    @extend_schema(summary='List active couriers.', tags=['logistics'])
    def get(self, request):
        qs = Courier.objects.filter(is_active=True)
        return Response(CourierSerializer(qs, many=True).data)


# =============================================================================
# POST /api/v1/logistics/guides/  — create
# =============================================================================

class ShipmentGuideListCreateView(_AdminOnly, APIView):
    @extend_schema(summary='List shipment guides.', tags=['logistics'],
                   operation_id='logistics_guides_list')
    def get(self, request):
        qs = ShipmentGuide.objects.select_related('order', 'courier').order_by('-created_at')
        return Response(ShipmentGuideSerializer(qs, many=True).data)

    @extend_schema(
        summary='Create shipment guide.',
        request=ShipmentGuideCreateSerializer,
        responses={201: ShipmentGuideSerializer},
        tags=['logistics'],
    )
    @transaction.atomic
    def post(self, request):
        ser = ShipmentGuideCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        guide = ser.save()
        ShipmentEvent.objects.create(
            guide=guide,
            status=guide.status,
            description='Guia creada.',
            occurred_at=timezone.now(),
            recorded_by=request.user if request.user.is_authenticated else None,
        )
        return Response(
            ShipmentGuideSerializer(guide).data, status=status.HTTP_201_CREATED,
        )


# =============================================================================
# PATCH /api/v1/logistics/guides/<pk>/  — update status
# =============================================================================

class ShipmentGuideDetailView(_AdminOnly, APIView):
    @extend_schema(summary='Shipment guide detail.', tags=['logistics'],
                   operation_id='logistics_guides_retrieve')
    def get(self, request, pk):
        try:
            guide = ShipmentGuide.objects.select_related('order', 'courier').get(pk=pk)
        except ShipmentGuide.DoesNotExist:
            raise NotFound({'detail': 'Guia no encontrada.',
                            'codigo_error': 'GUIA_NO_ENCONTRADA'})
        data = ShipmentGuideSerializer(guide).data
        data['events'] = ShipmentEventSerializer(guide.events.all(), many=True).data
        return Response(data)

    @extend_schema(
        summary='Update shipment status.',
        tags=['logistics'],
    )
    @transaction.atomic
    def patch(self, request, pk):
        try:
            guide = ShipmentGuide.objects.select_for_update().get(pk=pk)
        except ShipmentGuide.DoesNotExist:
            raise NotFound({'detail': 'Guia no encontrada.',
                            'codigo_error': 'GUIA_NO_ENCONTRADA'})

        new_status = request.data.get('status')
        if not new_status:
            raise ValidationError({
                'detail': 'status requerido.',
                'codigo_error': 'STATUS_REQUERIDO',
            })
        valid_codes = {code for code, _ in ShipmentGuide.STATUSES}
        if new_status not in valid_codes:
            raise ValidationError({
                'detail': f'status invalido: {new_status}.',
                'codigo_error': 'STATUS_INVALIDO',
            })

        description = (request.data.get('description') or '').strip()
        guide.status = new_status
        if new_status == ShipmentGuide.STATUS_DELIVERED and not guide.delivered_at:
            guide.delivered_at = timezone.now()
        guide.save(update_fields=['status', 'delivered_at', 'updated_at'])

        ShipmentEvent.objects.create(
            guide=guide,
            status=new_status,
            description=description,
            occurred_at=timezone.now(),
            recorded_by=request.user if request.user.is_authenticated else None,
        )

        return Response(ShipmentGuideSerializer(guide).data)


# =============================================================================
# POST /api/v1/logistics/guides/<pk>/confirm-delivery/  — UC-LOG-05
# =============================================================================

class ConfirmDeliveryView(_AdminOnly, APIView):
    @extend_schema(
        summary='Confirm delivery (UC-LOG-05). Idempotent.',
        tags=['logistics'],
    )
    @transaction.atomic
    def post(self, request, pk):
        try:
            guide = ShipmentGuide.objects.select_for_update().get(pk=pk)
        except ShipmentGuide.DoesNotExist:
            raise NotFound({
                'detail': 'Guia no encontrada.',
                'codigo_error': 'GUIA_NO_ENCONTRADA',
            })

        if guide.status == ShipmentGuide.STATUS_CANCELLED:
            raise ValidationError({
                'detail': 'No se puede confirmar la entrega de una guia cancelada.',
                'codigo_error': 'GUIA_CANCELADA',
            })

        already = guide.status == ShipmentGuide.STATUS_DELIVERED
        if not already:
            guide.status = ShipmentGuide.STATUS_DELIVERED
            guide.delivered_at = timezone.now()
            guide.save(update_fields=['status', 'delivered_at', 'updated_at'])
            ShipmentEvent.objects.create(
                guide=guide,
                status=ShipmentGuide.STATUS_DELIVERED,
                description='Entrega confirmada.',
                occurred_at=guide.delivered_at,
                recorded_by=request.user if request.user.is_authenticated else None,
            )
            # Sync order status (best effort).
            order = guide.order
            if order.status != Order.STATUS_DELIVERED:
                order.status = Order.STATUS_DELIVERED
                order.save(update_fields=['status', 'updated_at'])

        return Response({
            'id': guide.id,
            'status': guide.status,
            'delivered_at': guide.delivered_at,
            'already_delivered': already,
        })
