"""Recorrido del comprador sobre su propia venta — UC-ORD-02/03/04.

Restaura los tres endpoints que servía el addon espejo ``orders`` antes de su
retiro (SOL-098, ``api@77bd1f0``), reanclados a la venta canónica.

**Por qué viven aquí y no en otro addon.** La referencia parte la superficie
de órdenes en dos familias: ``sale/controllers/portal.py`` expone
``/my/orders``, ``/my/orders/<id>`` y ``/my/orders/<id>/decline`` —el
comprador **consulta** su orden y la cancela—, mientras el **checkout**
(carrito → pago → confirmación) es de ``website_sale``. El espejo mezclaba
ambas en un solo addon; por eso al retirarlo quedaron huérfanas piezas de
naturaleza distinta. Ver ``analisis-hogar-de-g4-segun-referencia-odoo``.

Lo que **no** se restaura aquí, y por qué:

- ``POST /api/v2/orders/`` (checkout) — su hogar es ``website_sale``, que
  todavía no existe en el árbol. Crearlo es una decisión estructural, no un
  fix de reconexión.
- ``shipping-address`` / ``shipping-method`` — el primero es
  ``/shop/update_address`` de ``website_sale``; el segundo está deprecado
  desde 2026-07-07 (el comprador no elige transportista: el envío se deriva
  por zona).
"""
import logging

from drf_spectacular.utils import (
    OpenApiParameter, OpenApiResponse, extend_schema,
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.authz.permissions import HasCapability
from addons.observability.audit import audit_log_business
from addons.observability.models import BusinessEvent

from .models import SaleOrder
from .serializers import (
    CancelOrderSerializer, OrderListSerializer, OrderSerializer,
)
from .services import cancel_order
from .status_projection import CANONICAL_ORDER_STATUSES, filter_orders_by_status

logger = logging.getLogger('apps')


class OrderPagination(PageNumberPagination):
    """RNF-PERF-003: 10 por página, ajustable hasta 50."""
    page_size             = 10
    page_size_query_param = 'page_size'
    max_page_size         = 50


def _own_orders(user):
    """Ventas confirmadas del comprador, listas para serializar sin N+1.

    Excluye los borradores: un draft es el carrito, no una orden que el
    comprador reconozca en su historial.
    """
    return (
        SaleOrder.objects
        .filter(partner=user)
        .exclude(state=SaleOrder.STATE_DRAFT)
        .select_related('carrier', 'delivery_address')
        .prefetch_related('order_line__product__images',
                          'order_line__variant__option', 'payments',
                          'shipment_guide')
        .order_by('-created_at')
    )


class OrderListView(APIView):
    """GET ``/api/v2/orders/`` — historial del comprador (UC-ORD-03)."""
    permission_classes  = [IsAuthenticated, HasCapability]
    required_capability = 'account.orders'

    @extend_schema(
        summary='Historial de órdenes del comprador',
        description=(
            'Lista las órdenes del comprador, paginadas (10 por página). '
            'Incluye miniatura de la primera partida, total y conteo. '
            'Filtro opcional ``?status=`` sobre el vocabulario canónico.'
        ),
        parameters=[
            OpenApiParameter('page', int, description='Número de página'),
            OpenApiParameter('page_size', int,
                             description='Órdenes por página (máx. 50)'),
            OpenApiParameter('status', str,
                             description='Estado proyectado por el que filtrar'),
        ],
        responses={
            200: OrderListSerializer(many=True),
            400: OpenApiResponse(description='INVALID_STATUS'),
        },
        tags=['orders'],
        operation_id='orders_list',
    )
    def get(self, request):
        queryset = _own_orders(request.user)

        # El filtro se traduce a los ejes canónicos: ``status`` nunca fue una
        # columna que se pudiera comparar. Los valores muertos del enum legacy
        # quedan fuera del vocabulario y dan 400 en vez de una lista vacía.
        status_filter = request.query_params.get('status')
        if status_filter:
            try:
                queryset = filter_orders_by_status(queryset, status_filter)
            except ValueError:
                return Response(
                    {'detail': (f'Status inválido: {status_filter}. Válidos: '
                                f'{list(CANONICAL_ORDER_STATUSES)}.'),
                     'codigo_error': 'INVALID_STATUS'},
                    status=400,
                )

        paginator  = OrderPagination()
        page       = paginator.paginate_queryset(queryset, request)
        serializer = OrderListSerializer(page, many=True,
                                         context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class OrderDetailView(APIView):
    """GET ``/api/v2/orders/<order_number>/`` — detalle (UC-ORD-02)."""
    permission_classes  = [IsAuthenticated, HasCapability]
    required_capability = 'account.orders'

    @extend_schema(
        summary='Detalle de una orden',
        description=(
            'Snapshot completo: partidas con el precio del momento de la '
            'compra (BR-005), dirección de entrega, desglose de importes y '
            'estado proyectado. RNF-SEC-003: 404 si la orden no existe **o** '
            'no es del comprador — la misma respuesta, para no filtrar la '
            'existencia de órdenes ajenas.'
        ),
        responses={
            200: OrderSerializer,
            404: OpenApiResponse(description='ORDER_NOT_FOUND'),
        },
        tags=['orders'],
        operation_id='orders_retrieve',
    )
    def get(self, request, order_number):
        order = _own_orders(request.user).filter(name=order_number).first()
        if order is None:
            return Response(
                {'detail': 'Orden no encontrada.',
                 'codigo_error': 'ORDER_NOT_FOUND'},
                status=404,
            )
        return Response(
            OrderSerializer(order, context={'request': request}).data)


class OrderCancelView(APIView):
    """POST ``/api/v2/orders/<order_number>/cancellations/`` — UC-ORD-04.

    Análogo de ``/my/orders/<id>/decline`` de la referencia.
    """
    permission_classes  = [IsAuthenticated, HasCapability]
    required_capability = 'account.orders'

    @extend_schema(
        summary='Cancelar una orden',
        description=(
            'Cancela una orden aún no despachada, restaura el stock de sus '
            'partidas y, si había un pago aprobado, dispara el reembolso. '
            'Una vez enviada, la vuelta atrás es una devolución, no una '
            'cancelación.'
        ),
        request=CancelOrderSerializer,
        responses={
            200: OrderSerializer,
            400: OpenApiResponse(description='CANCELLATION_NOT_ALLOWED'),
            404: OpenApiResponse(description='ORDER_NOT_FOUND'),
            503: OpenApiResponse(description='GATEWAY_UNAVAILABLE'),
        },
        tags=['orders'],
    )
    def post(self, request, order_number):
        order = _own_orders(request.user).filter(name=order_number).first()
        if order is None:
            return Response(
                {'detail': 'Orden no encontrada.',
                 'codigo_error': 'ORDER_NOT_FOUND'},
                status=404,
            )

        serializer = CancelOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get('reason', '')

        try:
            cancel_order(order=order, reason=reason, cancelled_by=request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc),
                 'codigo_error': 'CANCELLATION_NOT_ALLOWED'},
                status=400,
            )
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc), 'codigo_error': 'GATEWAY_UNAVAILABLE'},
                status=503,
            )

        audit_log_business(
            request.user, BusinessEvent.ACTION_ORDER_CANCELLED, request,
            target_type=BusinessEvent.TARGET_ORDER, target_id=order.pk,
            extra={'order_number': order.name, 'reason': reason},
        )

        # Re-consultar con los prefetch: ``cancel_order`` devuelve la instancia
        # bloqueada, sin ellos, y serializarla dispararía N+1.
        order = _own_orders(request.user).filter(pk=order.pk).first()
        return Response(
            OrderSerializer(order, context={'request': request}).data)
