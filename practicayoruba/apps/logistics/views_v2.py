"""
Views v2 — apps.logistics F5 (§1.3).

Tier A: ShipmentListCreateV2View, ShipmentDetailV2View,
        ShipmentCancellationV2View, ShipmentDeliveryV2View,
        BuyerOrderShipmentV2View
Tier B: ShipmentProblemReportV2View — takes shipment pk
        and resolves order_id before delegating.
"""
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.views import APIView

from .models import ShipmentGuide
from .views import (
    BuyerGuideView,
    BuyerReportIncidentView,
    CancelGuideView,
    ConfirmDeliveryView,
    ShipmentGuideDetailView,
    ShipmentGuideListCreateView,
)


class ShipmentListCreateV2View(APIView):
    """GET|POST /api/v2/shipments/ — Tier A."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        return ShipmentGuideListCreateView().get(request)

    def post(self, request):
        return ShipmentGuideListCreateView().post(request)


class ShipmentDetailV2View(APIView):
    """GET|PATCH /api/v2/shipments/<pk>/ — Tier A."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, pk):
        return ShipmentGuideDetailView().get(request, pk)

    def patch(self, request, pk):
        return ShipmentGuideDetailView().patch(request, pk)


class ShipmentCancellationV2View(APIView):
    """POST /api/v2/shipments/<pk>/cancellations/ — Tier A."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, pk):
        return CancelGuideView().post(request, pk)


class ShipmentDeliveryV2View(APIView):
    """POST /api/v2/shipments/<pk>/deliveries/ — Tier A."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, pk):
        return ConfirmDeliveryView().post(request, pk)


class BuyerOrderShipmentV2View(APIView):
    """GET /api/v2/orders/<order_id>/shipment/ — Tier A."""
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        return BuyerGuideView().get(request, order_id)


class ShipmentProblemReportV2View(APIView):
    """POST /api/v2/shipments/<pk>/problem-reports/ — Tier B.

    v1 was order-scoped (order_id in path); v2 is shipment-scoped.
    Resolve order_id from shipment before delegating to BuyerReportIncidentView.
    Ownership verification (order.user == request.user) happens inside the v1
    view (EX-01 secrecy: ORDER_NOT_FOUND if user does not own the order).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            guide = ShipmentGuide.objects.select_related('order').get(
                pk=pk, is_deleted=False,
            )
        except ShipmentGuide.DoesNotExist:
            raise NotFound(
                {'detail': 'Envío no encontrado.', 'codigo_error': 'SHIPMENT_GUIDE_NOT_FOUND'}
            )
        return BuyerReportIncidentView().post(request, guide.order_id)
