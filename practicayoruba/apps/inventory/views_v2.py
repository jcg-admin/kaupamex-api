"""Views v2 — apps.inventory admin (F4 migrar-urls-rest-v2)."""
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .views import (
    StockAdjustView,
    StockAlertResolveView,
    VariantRestockView,
    VariantStockAdjustView,
)

_VALID_ALERT_ACTIONS = {'resolve'}


class StockAdjustV2View(APIView):
    """
    PATCH /api/v2/admin/inventory/<product_pk>/

    Tier B: POST /adjust/ → PATCH directo sobre el recurso.
    Delega la logica de negocio a StockAdjustView.post().
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, product_pk):
        return StockAdjustView().post(request, product_pk)


class VariantStockV2View(APIView):
    """
    PATCH /api/v2/admin/inventory/variants/<variant_pk>/

    Tier B: POST /adjust/ → PATCH sobre la variante.
    Delega a VariantStockAdjustView.post().
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, variant_pk):
        return VariantStockAdjustView().post(request, variant_pk)


class VariantRestocksV2View(APIView):
    """
    POST /api/v2/admin/inventory/variants/<variant_pk>/restocks/

    Tier A rename: /restock/ → /restocks/ (plural canonico REST).
    Delega a VariantRestockView.post().
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, variant_pk):
        return VariantRestockView().post(request, variant_pk)


class StockAlertStatusV2View(APIView):
    """
    PATCH /api/v2/admin/inventory/alerts/<pk>/

    Tier B: POST /alerts/<pk>/resolve/ → PATCH con {action: resolve}.
    Solo la accion 'resolve' esta soportada en esta version.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, pk):
        action = request.data.get('action')
        if action not in _VALID_ALERT_ACTIONS:
            return Response(
                {'detail': 'Accion no valida.', 'codigo_error': 'INVALID_ACTION'},
                status=400,
            )
        return StockAlertResolveView().post(request, pk)
