"""Admin views v2 — apps.catalogue (F4 migrar-urls-rest-v2)."""
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .price_sync_views import (
    PriceSyncApplyCSVView,
    PriceSyncApplyPercentageView,
    PriceSyncPreviewCSVView,
    PriceSyncPreviewPercentageView,
)
from .product_discount_views import ProductDiscountDeactivateView

_PRICE_SYNC_HANDLERS = {
    ('preview', 'csv'):        PriceSyncPreviewCSVView,
    ('apply',   'csv'):        PriceSyncApplyCSVView,
    ('preview', 'percentage'): PriceSyncPreviewPercentageView,
    ('apply',   'percentage'): PriceSyncApplyPercentageView,
}


class ProductDiscountStatusV2View(APIView):
    """
    PATCH /api/v2/admin/product-discounts/<pk>/

    Tier B: POST /deactivate/ → PATCH con {active: false}.
    Unico valor aceptado: active=false (o "false"/"0").
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, pk):
        active = request.data.get('active')
        if active is not False and str(active).lower() not in ('false', '0'):
            return Response(
                {'detail': 'Solo se acepta active=false.', 'codigo_error': 'INVALID_ACTION'},
                status=400,
            )
        return ProductDiscountDeactivateView().post(request, pk)


class PriceSyncsV2View(APIView):
    """
    POST /api/v2/admin/price-syncs/

    Tier B: consolida los cuatro endpoints v1 de price-sync en uno solo.
    El body debe incluir:
      type: "preview" | "apply"
      mode: "csv" | "percentage"
    Los parametros adicionales (file, pct, session_id) siguen igual.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

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
