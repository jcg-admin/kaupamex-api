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
from .serializers import BuyerShipmentGuideSerializer, CourierCreateUpdateSerializer, CourierSerializer, ShipmentEventSerializer, ShipmentGuideCreateSerializer, ShipmentGuideSerializer
from apps.notifications.service import notify_shipping_updated




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
        responses={200: ShipmentGuideSerializer(many=True)},
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
                    'codigo_error': 'COURIER_ID_INVALID',
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
    @extend_schema(summary='List active couriers.', tags=['logistics'],
                   responses={200: CourierSerializer(many=True)})
    def get(self, request):
        qs = Courier.objects.filter(is_active=True)
        return Response(CourierSerializer(qs, many=True).data)

    @extend_schema(
        summary='Create courier.',
        request=CourierCreateUpdateSerializer,
        responses={201: CourierSerializer},
        tags=['logistics'],
    )
    def post(self, request):
        ser = CourierCreateUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        courier = ser.save()
        return Response(CourierSerializer(courier).data, status=status.HTTP_201_CREATED)


class CourierDetailView(_AdminOnly, APIView):
    @extend_schema(
        summary='Update courier.',
        request=CourierCreateUpdateSerializer,
        responses={200: CourierSerializer, 404: None},
        tags=['logistics'],
    )
    def patch(self, request, pk):
        try:
            courier = Courier.objects.get(pk=pk)
        except Courier.DoesNotExist:
            raise NotFound({'detail': 'Paqueteria no encontrada.',
                            'codigo_error': 'COURIER_NOT_FOUND'})
        ser = CourierCreateUpdateSerializer(courier, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        courier = ser.save()
        return Response(CourierSerializer(courier).data)

    @extend_schema(
        summary='Deactivate courier (soft-disable).',
        responses={200: None, 404: None},
        tags=['logistics'],
    )
    def delete(self, request, pk):
        try:
            courier = Courier.objects.get(pk=pk)
        except Courier.DoesNotExist:
            raise NotFound({'detail': 'Paqueteria no encontrada.',
                            'codigo_error': 'COURIER_NOT_FOUND'})
        courier.is_active = False
        courier.save(update_fields=['is_active', 'updated_at'])
        return Response({'deactivated': True, 'id': courier.id})


# =============================================================================
# POST /api/v1/logistics/guides/  — create
# =============================================================================

class ShipmentGuideListCreateView(_AdminOnly, APIView):
    @extend_schema(summary='List shipment guides.', tags=['logistics'],
                   operation_id='logistics_guides_list',
                   responses={200: ShipmentGuideSerializer(many=True)})
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
        # UC-LOG-01 POST-01: transition order to SHIPPED.
        if guide.order.status == Order.STATUS_IN_PREPARATION:
            guide.order.status = Order.STATUS_SHIPPED
            guide.order.save(update_fields=['status', 'updated_at'])
        ShipmentEvent.objects.create(
            guide=guide,
            status=guide.status,
            description='Guia creada.',
            occurred_at=timezone.now(),
            recorded_by=request.user if request.user.is_authenticated else None,
        )
        notify_shipping_updated(
            order=guide.order,
            user=guide.order.user,
            tracking_number=guide.tracking_number,
            event_description='Guia creada.',
        )
        return Response(
            ShipmentGuideSerializer(guide).data, status=status.HTTP_201_CREATED,
        )


# =============================================================================
# PATCH /api/v1/logistics/guides/<pk>/  — update status
# =============================================================================

class ShipmentGuideDetailView(_AdminOnly, APIView):
    @extend_schema(summary='Shipment guide detail.', tags=['logistics'],
                   operation_id='logistics_guides_retrieve',
                   responses={200: ShipmentGuideSerializer, 404: None})
    def get(self, request, pk):
        try:
            guide = ShipmentGuide.objects.select_related('order', 'courier').get(pk=pk)
        except ShipmentGuide.DoesNotExist:
            raise NotFound({'detail': 'Guia no encontrada.',
                            'codigo_error': 'SHIPMENT_GUIDE_NOT_FOUND'})
        data = ShipmentGuideSerializer(guide).data
        data['events'] = ShipmentEventSerializer(guide.events.all(), many=True).data
        return Response(data)

    @extend_schema(
        summary='Update shipment status.',
        tags=['logistics'],
        responses={200: ShipmentGuideSerializer, 400: None, 404: None},
    )
    @transaction.atomic
    def patch(self, request, pk):
        try:
            guide = ShipmentGuide.objects.select_for_update().get(pk=pk)
        except ShipmentGuide.DoesNotExist:
            raise NotFound({'detail': 'Guia no encontrada.',
                            'codigo_error': 'SHIPMENT_GUIDE_NOT_FOUND'})

        new_status = request.data.get('status')
        if not new_status:
            raise ValidationError({
                'detail': 'status requerido.',
                'codigo_error': 'STATUS_REQUIRED',
            })
        valid_codes = {code for code, _ in ShipmentGuide.STATUSES}
        if new_status not in valid_codes:
            raise ValidationError({
                'detail': f'status invalido: {new_status}.',
                'codigo_error': 'STATUS_INVALID',
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
        notify_shipping_updated(
            order=guide.order,
            user=guide.order.user,
            tracking_number=guide.tracking_number,
            event_description=description or f'Estado actualizado a: {new_status}.',
        )

        return Response(ShipmentGuideSerializer(guide).data)


# =============================================================================
# POST /api/v1/logistics/guides/<pk>/cancel/  — UC-LOG-01 Alt-C
# =============================================================================

class CancelGuideView(_AdminOnly, APIView):
    @extend_schema(
        summary='Cancel shipment guide (UC-LOG-01 Alt-C). Soft-delete preserves audit trail.',
        responses={200: None, 400: None, 404: None},
        tags=['logistics'],
    )
    @transaction.atomic
    def post(self, request, pk):
        try:
            guide = ShipmentGuide.objects.select_for_update().get(pk=pk)
        except ShipmentGuide.DoesNotExist:
            raise NotFound({'detail': 'Guia no encontrada.',
                            'codigo_error': 'SHIPMENT_GUIDE_NOT_FOUND'})
        if guide.status == ShipmentGuide.STATUS_DELIVERED:
            raise ValidationError({
                'detail': 'No se puede cancelar una guia entregada.',
                'codigo_error': 'SHIPMENT_GUIDE_DELIVERED',
            })
        if guide.status == ShipmentGuide.STATUS_CANCELLED:
            raise ValidationError({
                'detail': 'La guia ya esta cancelada.',
                'codigo_error': 'SHIPMENT_GUIDE_ALREADY_CANCELLED',
            })
        reason = (request.data.get('reason') or 'Guia cancelada.').strip()
        guide.status = ShipmentGuide.STATUS_CANCELLED
        guide.save(update_fields=['status', 'updated_at'])
        ShipmentEvent.objects.create(
            guide=guide,
            status=ShipmentGuide.STATUS_CANCELLED,
            description=reason,
            occurred_at=timezone.now(),
            recorded_by=request.user if request.user.is_authenticated else None,
        )
        guide.delete()  # soft-delete preserves audit history (DEC-DOC-007)
        return Response({'cancelled': True, 'id': pk})


# =============================================================================
# POST /api/v1/logistics/guides/<pk>/confirm-delivery/  — UC-LOG-05
# =============================================================================

class ConfirmDeliveryView(_AdminOnly, APIView):
    @extend_schema(
        summary='Confirm delivery (UC-LOG-05). Idempotent.',
        tags=['logistics'],
        responses={200: ShipmentGuideSerializer, 400: None, 404: None},
    )
    @transaction.atomic
    def post(self, request, pk):
        try:
            guide = ShipmentGuide.objects.select_for_update().get(pk=pk)
        except ShipmentGuide.DoesNotExist:
            raise NotFound({
                'detail': 'Guia no encontrada.',
                'codigo_error': 'SHIPMENT_GUIDE_NOT_FOUND',
            })

        if guide.status == ShipmentGuide.STATUS_CANCELLED:
            raise ValidationError({
                'detail': 'No se puede confirmar la entrega de una guia cancelada.',
                'codigo_error': 'SHIPMENT_GUIDE_CANCELLED',
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
            notify_shipping_updated(
                order=guide.order,
                user=guide.order.user,
                tracking_number=guide.tracking_number,
                event_description='Entrega confirmada.',
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


# =============================================================================
# GET /api/v1/logistics/buyer/order/<order_id>/guide/  — UC-LOG-03
# =============================================================================

class BuyerGuideView(APIView):
    """UC-LOG-03: buyer sees shipment guide for their own order."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Buyer: shipment guide for own order (UC-LOG-03).',
        responses={200: BuyerShipmentGuideSerializer, 404: None},
        tags=['logistics'],
    )
    def get(self, request, order_id):
        try:
            order = Order.objects.get(pk=order_id, user=request.user)
        except Order.DoesNotExist:
            raise NotFound({'detail': 'Orden no encontrada.',
                            'codigo_error': 'ORDER_NOT_FOUND'})
        try:
            guide = (
                ShipmentGuide.objects
                .select_related('courier')
                .prefetch_related('events')
                .get(order=order)
            )
        except ShipmentGuide.DoesNotExist:
            raise NotFound({'detail': 'Guia de envio no encontrada.',
                            'codigo_error': 'SHIPMENT_GUIDE_NOT_FOUND'})
        return Response(BuyerShipmentGuideSerializer(guide).data)
