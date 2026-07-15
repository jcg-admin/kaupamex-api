"""Admin views — apps.catalogue (F8 consolidation)."""
from rest_framework.permissions import IsAuthenticated
from apps.authz.permissions import HasCapability
from rest_framework.response import Response
from rest_framework.views import APIView

from .price_sync_views import (
    PriceSyncApplyCSVView,
    PriceSyncApplyPercentageView,
    PriceSyncPreviewCSVView,
    PriceSyncPreviewPercentageView,
)
from .product_discount_views import ProductDiscountDeactivateView, ProductDiscountDetailView

_PRICE_SYNC_HANDLERS = {
    ('preview', 'csv'):        PriceSyncPreviewCSVView,
    ('apply',   'csv'):        PriceSyncApplyCSVView,
    ('preview', 'percentage'): PriceSyncPreviewPercentageView,
    ('apply',   'percentage'): PriceSyncApplyPercentageView,
}


class ProductDiscountStatusV2View(APIView):
    """
    PATCH /api/v2/admin/product-discounts/<pk>/

    Unified edit endpoint (UC-DASH-03 + Tier B deactivation).
    - {active: false}  → deactivate
    - {discount_pct, ...} → partial update
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'catalogue.edit'

    def patch(self, request, pk):
        active = request.data.get('active')
        if active is not None:
            if active is False or str(active).lower() == 'false':
                return ProductDiscountDeactivateView().post(request, pk)
            return Response(
                {'detail': 'Solo se acepta active=false.', 'codigo_error': 'INVALID_ACTION'},
                status=400,
            )
        return ProductDiscountDetailView().patch(request, pk)


class PriceSyncsV2View(APIView):
    """
    POST /api/v2/admin/price-syncs/

    Consolidates four v1 price-sync endpoints.
    Body must include type ('preview'|'apply') and mode ('csv'|'percentage').
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'catalogue.edit'

    def post(self, request):
        type_ = request.data.get('type')
        mode  = request.data.get('mode')
        handler_cls = _PRICE_SYNC_HANDLERS.get((type_, mode))
        if handler_cls is None:
            return Response(
                {'detail': 'type o mode invalidos.', 'codigo_error': 'INVALID_ACTION'},
                status=400,
            )
        return handler_cls().post(request)
