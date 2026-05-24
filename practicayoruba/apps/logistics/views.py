"""
Views — apps.logistics (P-10 / UC-LOG-01..09).
"""
import logging
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger('apps')

from apps.orders.models import Order
from .models import Courier, ShipmentEvent, ShipmentGuide
from .serializers import (
    BuyerShipmentGuideSerializer, CourierCreateUpdateSerializer, CourierSerializer,
    ShipmentGuideCreateSerializer, ShipmentGuideSerializer,
)


class _AdminOnly:
    permission_classes = [IsAuthenticated, IsAdminUser]


class LogisticsPanelView(_AdminOnly, APIView):
    @extend_schema(summary='Panel logístico (UC-LOG-01)', tags=['logistics'], responses={200: None})
    def get(self, request):
        courier_id_raw = request.query_params.get('courier_id')
        courier_filter = None
        if courier_id_raw is not None:
            try:
                courier_filter = int(courier_id_raw)
            except ValueError:
                return Response({'detail': 'courier_id inválido.', 'codigo_error': 'COURIER_ID_INVALID'}, status=400)

        group_a_qs = Order.objects.filter(status=Order.STATUS_IN_PREPARATION).select_related('address').prefetch_related('items')
        pending_pickup = []
        for order in group_a_qs:
            entry = {'order_id': order.id, 'order_number': order.order_number, 'status': order.status}
            try:
                addr = order.address
                entry['recipient_name'] = addr.recipient_name
                entry['city'] = addr.city
            except Exception:
                logger.warning('Order %s has no address record', order.id)
            pending_pickup.append(entry)

        guide_qs = ShipmentGuide.objects.filter(is_deleted=False).exclude(
            status=ShipmentGuide.STATUS_DELIVERED,
        ).exclude(status=ShipmentGuide.STATUS_CANCELLED).select_related('order', 'courier')
        if courier_filter:
            guide_qs = guide_qs.filter(courier_id=courier_filter)

        in_transit = []
        for guide in guide_qs:
            in_transit.append({
                'guide_id': guide.id, 'tracking_number': guide.tracking_number,
                'order_id': guide.order_id, 'order_number': guide.order.order_number,
                'courier_code': guide.courier.code, 'status': guide.status,
            })

        return Response({'group_a_count': len(pending_pickup), 'group_b_count': len(in_transit),
                         'pending_pickup': pending_pickup, 'in_transit': in_transit})


class CourierListCreateView(_AdminOnly, APIView):
    def get(self, request):
        return Response(CourierSerializer(Courier.objects.all().order_by('name'), many=True).data)

    def post(self, request):
        ser = CourierCreateUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response(CourierSerializer(ser.save()).data, status=201)


class CourierDetailView(_AdminOnly, APIView):
    def _get(self, pk):
        try:
            return Courier.objects.get(pk=pk)
        except Courier.DoesNotExist:
            raise NotFound({'detail': 'Courier no encontrado.', 'codigo_error': 'COURIER_NOT_FOUND'})

    def patch(self, request, pk):
        courier = self._get(pk)
        ser = CourierCreateUpdateSerializer(courier, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(CourierSerializer(courier).data)

    def delete(self, request, pk):
        courier = self._get(pk)
        courier.is_active = False
        courier.save(update_fields=['is_active'])
        return Response({'deactivated': True})


class ShipmentGuideListCreateView(_AdminOnly, APIView):
    def get(self, request):
        qs = ShipmentGuide.objects.filter(is_deleted=False).select_related('order', 'courier').order_by('-created_at')
        if request.query_params.get('order_id'):
            qs = qs.filter(order_id=request.query_params['order_id'])
        return Response(ShipmentGuideSerializer(qs, many=True).data)

    def post(self, request):
        ser = ShipmentGuideCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        order = data['order']
        guide = ShipmentGuide.objects.create(
            order=order, courier=data['courier'],
            tracking_number=data['tracking_number'], notes=data.get('notes', ''),
        )
        order.status = Order.STATUS_SHIPPED
        order.save(update_fields=['status'])
        return Response(ShipmentGuideSerializer(guide).data, status=201)


class ShipmentGuideDetailView(_AdminOnly, APIView):
    VALID_STATUSES = {s[0] for s in ShipmentGuide.STATUSES}

    def _get_guide(self, pk):
        try:
            return ShipmentGuide.objects.select_related('order', 'courier').get(pk=pk, is_deleted=False)
        except ShipmentGuide.DoesNotExist:
            raise NotFound({'detail': 'Guía no encontrada.', 'codigo_error': 'SHIPMENT_GUIDE_NOT_FOUND'})

    def get(self, request, pk):
        return Response(ShipmentGuideSerializer(self._get_guide(pk)).data)

    def patch(self, request, pk):
        guide = self._get_guide(pk)
        new_status = request.data.get('status')
        if not new_status or new_status not in self.VALID_STATUSES:
            return Response({'detail': f'Estado inválido: {new_status!r}.', 'codigo_error': 'STATUS_INVALID'}, status=400)
        guide.status = new_status
        guide.save(update_fields=['status', 'updated_at'])
        ShipmentEvent.objects.create(
            guide=guide, status=new_status,
            description=request.data.get('description', ''),
            occurred_at=timezone.now(), recorded_by=request.user,
        )
        return Response(ShipmentGuideSerializer(guide).data)


class ConfirmDeliveryView(_AdminOnly, APIView):
    def post(self, request, pk):
        try:
            guide = ShipmentGuide.objects.select_related('order').get(pk=pk, is_deleted=False)
        except ShipmentGuide.DoesNotExist:
            return Response({'detail': 'Guía no encontrada.', 'codigo_error': 'SHIPMENT_GUIDE_NOT_FOUND'}, status=404)
        if guide.status == ShipmentGuide.STATUS_CANCELLED:
            return Response({'detail': 'Guía cancelada.', 'codigo_error': 'SHIPMENT_GUIDE_CANCELLED'}, status=400)
        if guide.status == ShipmentGuide.STATUS_DELIVERED:
            return Response({'status': guide.status, 'already_delivered': True, 'tracking_number': guide.tracking_number})
        guide.status = ShipmentGuide.STATUS_DELIVERED
        guide.delivered_at = timezone.now()
        guide.save(update_fields=['status', 'delivered_at', 'updated_at'])
        guide.order.status = Order.STATUS_DELIVERED
        guide.order.save(update_fields=['status'])
        return Response({'status': guide.status, 'already_delivered': False,
                         'tracking_number': guide.tracking_number, 'delivered_at': guide.delivered_at})


class CancelGuideView(_AdminOnly, APIView):
    def post(self, request, pk):
        try:
            guide = ShipmentGuide.objects.select_related('order').get(pk=pk, is_deleted=False)
        except ShipmentGuide.DoesNotExist:
            return Response({'detail': 'Guía no encontrada.', 'codigo_error': 'SHIPMENT_GUIDE_NOT_FOUND'}, status=404)
        if guide.status == ShipmentGuide.STATUS_DELIVERED:
            return Response({'detail': 'No se puede cancelar una guía entregada.', 'codigo_error': 'SHIPMENT_GUIDE_DELIVERED'}, status=400)
        if guide.status == ShipmentGuide.STATUS_CANCELLED:
            return Response({'detail': 'La guía ya está cancelada.', 'codigo_error': 'SHIPMENT_GUIDE_ALREADY_CANCELLED'}, status=400)
        guide.status = ShipmentGuide.STATUS_CANCELLED
        guide.is_deleted = True
        guide.deleted_at = timezone.now()
        guide.save(update_fields=['status', 'is_deleted', 'deleted_at', 'updated_at'])
        return Response({'cancelled': True, 'tracking_number': guide.tracking_number})


class BuyerGuideView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        try:
            order = Order.objects.get(pk=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response({'detail': 'Orden no encontrada.', 'codigo_error': 'ORDER_NOT_FOUND'}, status=404)
        guide = ShipmentGuide.objects.filter(order=order, is_deleted=False).select_related('courier').first()
        if not guide:
            return Response({'detail': 'Guía de envío no disponible.', 'codigo_error': 'SHIPMENT_GUIDE_NOT_FOUND'}, status=404)
        return Response(BuyerShipmentGuideSerializer(guide, context={'request': request}).data)
