"""
Views — apps.logistics (P-10 / UC-LOG-01..09).

Admin:
  GET  /api/v1/admin/logistics/panel/          UC-LOG-01 panel logístico.
  GET  /api/v1/admin/logistics/couriers/       UC-LOG-02 listar courriers.
  GET  /api/v1/admin/logistics/shipments/      UC-LOG-03 listar guías.
  POST /api/v1/admin/logistics/shipments/      UC-LOG-04 crear guía.
  GET  /api/v1/admin/logistics/shipments/<id>/ UC-LOG-05 detalle guía.
  POST /api/v1/admin/logistics/shipments/<id>/confirm-delivery/ UC-LOG-06.
"""
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.orders.models import Order
from .models import Courier, ShipmentGuide
from .serializers import (
    CourierSerializer,
    ShipmentGuideCreateSerializer,
    ShipmentGuideSerializer,
)




class _AdminOnly:
    permission_classes = [IsAuthenticated, IsAdminUser]


class LogisticsPanelView(_AdminOnly, APIView):
    """GET /api/v1/admin/logistics/panel/ — UC-LOG-01."""

    @extend_schema(
        summary='Panel logístico (UC-LOG-01)',
        tags=['logistics'],
        responses={200: None},
    )
    def get(self, request):
        pending_shipment = Order.objects.filter(
            status=Order.STATUS_IN_PREPARATION
        ).count()
        shipped = Order.objects.filter(status=Order.STATUS_SHIPPED).count()
        delivered = Order.objects.filter(status=Order.STATUS_DELIVERED).count()
        return Response({
            'pending_shipment': pending_shipment,
            'shipped':          shipped,
            'delivered':        delivered,
        })


class CourierListView(_AdminOnly, APIView):
    """GET /api/v1/admin/logistics/couriers/ — UC-LOG-02."""

    @extend_schema(
        summary='Listar courriers (UC-LOG-02)',
        tags=['logistics'],
        responses={200: CourierSerializer(many=True)},
    )
    def get(self, request):
        couriers = Courier.objects.filter(is_active=True).order_by('name')
        return Response(CourierSerializer(couriers, many=True).data)


class ShipmentGuideListCreateView(_AdminOnly, APIView):
    """
    GET  /api/v1/admin/logistics/shipments/ — UC-LOG-03.
    POST /api/v1/admin/logistics/shipments/ — UC-LOG-04.
    """

    @extend_schema(
        summary='Listar guías de envío (UC-LOG-03)',
        parameters=[OpenApiParameter('order_id', int, required=False)],
        tags=['logistics'],
        responses={200: ShipmentGuideSerializer(many=True)},
    )
    def get(self, request):
        qs = ShipmentGuide.objects.all().select_related('order', 'courier').order_by('-created_at')
        order_id = request.query_params.get('order_id')
        if order_id:
            qs = qs.filter(order_id=order_id)
        return Response(ShipmentGuideSerializer(qs, many=True).data)

    @extend_schema(
        summary='Crear guía de envío (UC-LOG-04)',
        request=ShipmentGuideCreateSerializer,
        tags=['logistics'],
        responses={201: ShipmentGuideSerializer, 400: None, 404: None},
    )
    def post(self, request):
        ser = ShipmentGuideCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        try:
            order = Order.objects.get(pk=data['order_id'])
        except Order.DoesNotExist:
            raise NotFound({'detail': 'Orden no encontrada.',
                            'codigo_error': 'ORDER_NOT_FOUND'})

        if order.status not in (Order.STATUS_PAGADA, Order.STATUS_IN_PREPARATION):
            raise ValidationError({
                'detail': f'La orden debe estar en estado PAGADA o IN_PREPARATION para crear una guía. Estado actual: {order.status}.',
                'codigo_error': 'INVALID_ORDER_STATUS',
            })

        try:
            courier = Courier.objects.get(pk=data['courier_id'], is_active=True)
        except Courier.DoesNotExist:
            raise NotFound({'detail': 'Courrier no encontrado.',
                            'codigo_error': 'COURIER_NOT_FOUND'})

        guide = ShipmentGuide.objects.create(
            order=order,
            courier=courier,
            tracking_number=data['tracking_number'],
            notes=data.get('notes', ''),
        )
        order.status = Order.STATUS_SHIPPED
        order.save(update_fields=['status'])

        return Response(ShipmentGuideSerializer(guide).data, status=status.HTTP_201_CREATED)


class ShipmentGuideDetailView(_AdminOnly, APIView):
    """GET /api/v1/admin/logistics/shipments/<id>/ — UC-LOG-05."""

    @extend_schema(
        summary='Detalle de guía de envío (UC-LOG-05)',
        tags=['logistics'],
        responses={200: ShipmentGuideSerializer, 404: None},
    )
    def get(self, request, pk):
        try:
            guide = ShipmentGuide.objects.select_related('order', 'courier').get(pk=pk)
        except ShipmentGuide.DoesNotExist:
            raise NotFound({'detail': 'Guía no encontrada.',
                            'codigo_error': 'GUIDE_NOT_FOUND'})
        return Response(ShipmentGuideSerializer(guide).data)


class ConfirmDeliveryView(_AdminOnly, APIView):
    """POST /api/v1/admin/logistics/shipments/<id>/confirm-delivery/ — UC-LOG-06."""

    @extend_schema(
        summary='Confirmar entrega (UC-LOG-06)',
        tags=['logistics'],
        responses={200: ShipmentGuideSerializer, 400: None, 404: None},
    )
    def post(self, request, pk):
        try:
            guide = ShipmentGuide.objects.select_related('order').get(pk=pk)
        except ShipmentGuide.DoesNotExist:
            raise NotFound({'detail': 'Guía no encontrada.',
                            'codigo_error': 'GUIDE_NOT_FOUND'})

        if guide.order.status == Order.STATUS_DELIVERED:
            return Response(
                {'detail': 'La orden ya fue marcada como entregada.',
                 'codigo_error': 'ALREADY_DELIVERED'},
                status=400,
            )

        guide.order.status = Order.STATUS_DELIVERED
        guide.order.save(update_fields=['status'])
        guide.delivered_at = guide.order.updated_at
        guide.save(update_fields=['delivered_at'])

        return Response(ShipmentGuideSerializer(guide).data)


class BuyerGuideView(APIView):
    """GET /api/v1/logistics/buyer/order/<order_id>/guide/ — UC-LOG-07."""
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        from .serializers import BuyerShipmentGuideSerializer
        try:
            order = Order.objects.get(pk=order_id, user=request.user)
        except Order.DoesNotExist:
            raise NotFound({'detail': 'Orden no encontrada.', 'codigo_error': 'ORDER_NOT_FOUND'})

        guide = ShipmentGuide.objects.filter(order=order).select_related('courier').first()
        if not guide:
            raise NotFound({'detail': 'Guía de envío no disponible.', 'codigo_error': 'GUIDE_NOT_FOUND'})

        return Response(BuyerShipmentGuideSerializer(guide, context={'request': request}).data)


class CancelGuideView(APIView):
    """POST /api/v1/admin/logistics/guides/<pk>/cancel/ — UC-LOG-08."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, pk):
        try:
            guide = ShipmentGuide.objects.get(pk=pk)
        except ShipmentGuide.DoesNotExist:
            raise NotFound({'detail': 'Guía no encontrada.', 'codigo_error': 'GUIDE_NOT_FOUND'})

        if guide.status == ShipmentGuide.STATUS_CANCELLED:
            raise ValidationError({'detail': 'La guía ya está cancelada.', 'codigo_error': 'GUIDE_ALREADY_CANCELLED'})

        guide.status = ShipmentGuide.STATUS_CANCELLED
        guide.save(update_fields=['status', 'updated_at'])
        return Response(ShipmentGuideSerializer(guide).data)


class CourierDetailView(_AdminOnly, APIView):
    """PATCH /api/v1/admin/logistics/couriers/<pk>/ — UC-LOG-02."""
    from .serializers import CourierCreateUpdateSerializer

    def patch(self, request, pk):
        from .serializers import CourierCreateUpdateSerializer
        try:
            courier = Courier.objects.get(pk=pk)
        except Courier.DoesNotExist:
            raise NotFound({'detail': 'Courier no encontrado.', 'codigo_error': 'COURIER_NOT_FOUND'})
        ser = CourierCreateUpdateSerializer(courier, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(CourierSerializer(courier).data)
