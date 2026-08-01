"""Backoffice de ventas — UC-ORD-07 (detalle) y UC-ORD-09 (búsqueda).

Restaura los dos endpoints admin que servía el addon espejo ``orders`` antes
de su retiro (SOL-098, ``api@77bd1f0``). El destino lo deriva de la referencia
``analisis-hogar-de-g4-segun-referencia-odoo``: el backoffice es de
``sale_management``, no de ``sale`` —que sirve el recorrido del comprador— ni
de ``website_sale`` —que sirve el checkout—.

**Lo que no se restaura aquí, y por qué.** El espejo también exponía una
transición de estado admin (``PATCH .../status/``) y un dashboard. La
transición **no tiene traducción directa**: el estado dejó de ser una columna
que un administrador pueda fijar y pasó a proyectarse de tres ejes, así que
"cambiar el estado" es hoy "crear el hecho" (aprobar un pago, emitir una
guía), cada uno con su endpoint. El dashboard quedó declarado DESCONOCIDO en
el análisis: no tiene análogo medido en la referencia y no se le inventa
hogar. Ambos siguen abiertos en SOL-098.
"""
import logging
from datetime import date as dt_date

from drf_spectacular.utils import (
    OpenApiParameter, OpenApiResponse, extend_schema,
)
from django.db.models import Q
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.authz.permissions import HasCapability
from addons.sale.models import SaleOrder
from addons.sale.status_projection import (
    CANONICAL_ORDER_STATUSES, filter_orders_by_status,
)

from .serializers import AdminOrderSerializer

logger = logging.getLogger('apps')


class AdminOrderPagination(PageNumberPagination):
    """FR-ORD-09.02: 20 órdenes por página."""
    page_size             = 20
    page_size_query_param = 'page_size'
    max_page_size         = 100


def _admin_orders():
    """Todas las ventas confirmadas, listas para serializar sin N+1.

    Excluye los borradores: un draft es el carrito de alguien, no una orden
    que el backoffice deba gestionar.
    """
    return (
        SaleOrder.objects
        .exclude(state=SaleOrder.STATE_DRAFT)
        .select_related('partner', 'carrier', 'delivery_address')
        .prefetch_related('order_line__product__images',
                          'order_line__variant__option', 'payments',
                          'shipment_guide')
        .order_by('-created_at')
    )


class AdminOrderListView(APIView):
    """GET ``/api/v2/admin/orders/`` — búsqueda de órdenes (UC-ORD-09)."""
    permission_classes  = [IsAuthenticated, HasCapability]
    required_capability = 'orders.view'

    @extend_schema(
        summary='Listar y filtrar órdenes (admin)',
        description=(
            'Listado de las órdenes del sistema. Los filtros son acumulativos '
            '(AND) y la página trae 20. El filtro ``status`` se traduce a los '
            'ejes canónicos: un valor fuera del vocabulario da 400, no una '
            'lista vacía — una búsqueda mal escrita no debe parecer "sin '
            'resultados".'
        ),
        parameters=[
            OpenApiParameter('order_number', str,
                             description='Coincidencia parcial en la referencia'),
            OpenApiParameter('status', str, description='Estado proyectado'),
            OpenApiParameter('email', str,
                             description='Correo del cliente o del invitado'),
            OpenApiParameter('date_from', str, description='Desde (YYYY-MM-DD)'),
            OpenApiParameter('date_to', str, description='Hasta (YYYY-MM-DD)'),
            OpenApiParameter('page', int, description='Número de página'),
        ],
        responses={
            200: AdminOrderSerializer(many=True),
            400: OpenApiResponse(description='INVALID_STATUS · INVALID_DATE_FORMAT '
                                             '· INVALID_DATE_RANGE'),
        },
        tags=['orders-admin'],
        operation_id='admin_orders_list',
    )
    def get(self, request):
        queryset = _admin_orders()
        params   = request.query_params

        if order_number := params.get('order_number'):
            queryset = queryset.filter(name__icontains=order_number)

        if status_filter := params.get('status'):
            try:
                queryset = filter_orders_by_status(queryset, status_filter)
            except ValueError:
                raise ValidationError({
                    'status': (f'Estado inválido. Opciones válidas: '
                               f'{list(CANONICAL_ORDER_STATUSES)}'),
                    'codigo_error': 'INVALID_STATUS',
                })

        if email := params.get('email'):
            queryset = queryset.filter(
                Q(partner__email__icontains=email)
                | Q(guest_email__icontains=email)
            )

        date_from = params.get('date_from') or None
        date_to   = params.get('date_to') or None
        for label, value in (('date_from', date_from), ('date_to', date_to)):
            if value:
                try:
                    dt_date.fromisoformat(value)
                except ValueError:
                    raise ValidationError({
                        label: 'Formato inválido. Use YYYY-MM-DD.',
                        'codigo_error': 'INVALID_DATE_FORMAT',
                    })
        if date_from and date_to and date_from > date_to:
            raise ValidationError({
                'date_from': 'date_from no puede ser posterior a date_to.',
                'codigo_error': 'INVALID_DATE_RANGE',
            })
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        paginator = AdminOrderPagination()
        page      = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(
            AdminOrderSerializer(page, many=True,
                                 context={'request': request}).data)


class AdminOrderDetailView(APIView):
    """GET ``/api/v2/admin/orders/<order_number>/`` — detalle (UC-ORD-07).

    Sin restricción de propietario: el administrador ve cualquier orden. La
    capacidad es el gate, no la pertenencia.
    """
    permission_classes  = [IsAuthenticated, HasCapability]
    required_capability = 'orders.view'

    @extend_schema(
        summary='Detalle de orden (admin)',
        responses={
            200: AdminOrderSerializer,
            404: OpenApiResponse(description='ORDER_NOT_FOUND'),
        },
        tags=['orders-admin'],
        operation_id='admin_orders_retrieve',
    )
    def get(self, request, order_number):
        order = _admin_orders().filter(name=order_number).first()
        if order is None:
            return Response(
                {'detail': 'Orden no encontrada.',
                 'codigo_error': 'ORDER_NOT_FOUND'},
                status=404,
            )
        return Response(
            AdminOrderSerializer(order, context={'request': request}).data)
