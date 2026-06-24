"""Views v2 — apps.orders (F3 migrar-urls-rest-v2)."""
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .views import CheckoutView, OrderListView


class OrderCollectionV2View(APIView):
    """
    GET  /api/v2/orders/ — historial de ordenes del usuario (UC-ORD-03).
    POST /api/v2/orders/ — crear orden desde carrito / checkout (UC-ORD-01).

    Tier B (mapeo §2.2): coleccion REST canonica unificada. En v1 el
    checkout estaba en /api/v1/checkout/ (ruta separada); v2 lo ubica
    en POST /orders/ siguiendo la convencion REST de coleccion.
    GET requiere auth; POST acepta anonimos con throttle checkout.
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_throttles(self):
        if self.request.method == 'POST':
            self.throttle_scope = 'checkout'
            return [ScopedRateThrottle()]
        return []

    def get(self, request, *args, **kwargs):
        return OrderListView().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return CheckoutView().post(request)
