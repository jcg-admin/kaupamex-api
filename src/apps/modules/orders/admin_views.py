"""
Vistas Admin — apps.modules.orders
Sprint 19 — UC-ORD-07, UC-ORD-08, UC-ORD-09, UC-ORD-10
"""
import logging
from datetime import date as dt_date
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from apps.platform.authz.permissions import HasCapability
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from .serializers import AdminOrderSerializer
from .models import Order
from django.db.models import Q
from .admin_services import transition_order_status, admin_cancel_order, get_dashboard_data


logger = logging.getLogger('apps')


class AdminOrderPagination(PageNumberPagination):
    """20 órdenes por página para admin — FR-ORD-09.02."""
    page_size             = 20
    page_size_query_param = 'page_size'
    max_page_size         = 100


class AdminOrderListView(APIView):
    """
    GET /api/v1/admin/orders/
    Listado de todas las órdenes con filtros opcionales.
    UC-ORD-09 (FR-ORD-09.02). Paginado a 20 por página.
    Filtros: order_number, status, email, date_from, date_to.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'orders.view'

    @extend_schema(
        summary='Listar y filtrar órdenes (admin)',
        description=(
            'Listado de todas las órdenes del sistema. Filtros acumulativos (AND). '
            'Paginado a 20 por página. Solo administradores.'
        ),
        parameters=[
            OpenApiParameter('order_number', str, description='Coincidencia parcial en order_number'),
            OpenApiParameter('status',       str, description='Estado exacto (PENDING, PROCESSING…)'),
            OpenApiParameter('email',        str, description='Email del usuario o guest_email'),
            OpenApiParameter('date_from',    str, description='Fecha desde (YYYY-MM-DD)'),
            OpenApiParameter('date_to',      str, description='Fecha hasta (YYYY-MM-DD)'),
            OpenApiParameter('page',         int, description='Número de página'),
        ],
        responses={200: AdminOrderSerializer(many=True)},
        tags=['orders-admin'],
        operation_id='admin_orders_list',
    )
    def get(self, request):

        qs = (
            Order.objects.select_related('value', 'user', 'shipping_method')
            .prefetch_related('items')
            .order_by('-created_at')
        )

        # Aplicar filtros (FR-ORD-09.02 — todos acumulativos AND)
        params = request.query_params
        if order_number := params.get('order_number'):
            qs = qs.filter(order_number__icontains=order_number)
        if status := params.get('status'):
            # H-CICLO98-01: validate status against Order.STATUSES choices to
            # return 400 instead of silently returning an empty queryset.
            valid_statuses = {s[0] for s in Order.STATUSES}
            if status not in valid_statuses:
                raise ValidationError({
                    'status': f'Estado inválido. Opciones válidas: {sorted(valid_statuses)}',
                    'codigo_error': 'INVALID_STATUS',
                })
            qs = qs.filter(status=status)
        if email := params.get('email'):
            qs = qs.filter(
                Q(user__email__icontains=email) |
                Q(guest_email__icontains=email)
            )
        date_from = params.get('date_from') or None
        date_to   = params.get('date_to') or None
        if date_from:
            try:
                dt_date.fromisoformat(date_from)
            except ValueError:
                raise ValidationError({
                    'date_from': 'Formato inválido. Use YYYY-MM-DD.',
                    'codigo_error': 'INVALID_DATE_FORMAT',
                })
        if date_to:
            try:
                dt_date.fromisoformat(date_to)
            except ValueError:
                raise ValidationError({
                    'date_to': 'Formato inválido. Use YYYY-MM-DD.',
                    'codigo_error': 'INVALID_DATE_FORMAT',
                })
        if date_from and date_to and date_from > date_to:
            raise ValidationError({
                'date_from': 'date_from no puede ser posterior a date_to.',
                'codigo_error': 'INVALID_DATE_RANGE',
            })
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        paginator = AdminOrderPagination()
        page      = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(AdminOrderSerializer(page, many=True).data)


class AdminOrderDetailView(APIView):
    """
    GET /api/v1/admin/orders/<order_number>/
    Detalle completo de cualquier orden para admin.
    UC-ORD-07. Sin restricción de propietario (admin ve todo).
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'orders.view'

    @extend_schema(
        summary='Detalle de orden (admin)',
        description='Retorna el detalle completo. Sin restricción de propietario.',
        responses={
            200: AdminOrderSerializer,
            404: OpenApiResponse(description='Orden no encontrada.'),
        },
        tags=['orders-admin'],
        operation_id='admin_orders_retrieve',
    )
    def get(self, request, order_number):

        try:
            order = (
                Order.objects
                .select_related('value', 'address', 'shipping_method', 'user')
                .prefetch_related('items', 'status_logs__changed_by')
                .get(order_number=order_number)
            )
        except Order.DoesNotExist:
            return Response(
                {'detail': 'Orden no encontrada.', 'codigo_error': 'ORDER_NOT_FOUND'},
                status=404,
            )
        return Response(AdminOrderSerializer(order).data)


class AdminOrderStatusUpdateView(APIView):
    """
    PATCH /api/v1/admin/orders/<order_number>/status/
    Transiciona el estado de una orden según la máquina de estados.
    UC-ORD-07 (FR-ORD-07.02). Crea OrderStatusLog en cada transición.
    H-ADM-002: valida contra ALLOWED_TRANSITIONS con nombres reales del modelo.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'orders.edit'

    @extend_schema(
        summary='Cambiar estado de orden (admin)',
        description=(
            'Transiciona el estado de la orden validando la máquina de estados. '
            'Crea un registro en OrderStatusLog para auditoría. '
            'H-ADM-002: transiciones permitidas desde el estado actual.\n\n'
            'PENDING → PROCESSING | CANCELLED\n'
            'PROCESSING → IN_PREPARATION | CANCELLED\n'
            'IN_PREPARATION → SHIPPED\n'
            'SHIPPED → DELIVERED'
        ),
        request={'application/json': {
            'type': 'object',
            'properties': {
                'new_status': {'type': 'string'},
                'notes':      {'type': 'string'},
            },
            'required': ['new_status'],
        }},
        responses={
            200: AdminOrderSerializer,
            400: OpenApiResponse(description='Transición no permitida.'),
            404: OpenApiResponse(description='Orden no encontrada.'),
        },
        tags=['orders-admin'],
    )
    def patch(self, request, order_number):

        try:
            order = Order.objects.select_related('value', 'user').get(
                order_number=order_number
            )
        except Order.DoesNotExist:
            return Response(
                {'detail': 'Orden no encontrada.', 'codigo_error': 'ORDER_NOT_FOUND'},
                status=404,
            )

        new_status = request.data.get('new_status', '').strip()
        notes      = request.data.get('notes', '')

        if not new_status:
            return Response(
                {'detail': 'new_status es requerido.', 'codigo_error': 'FIELD_REQUIRED'},
                status=400,
            )

        try:
            transition_order_status(order, new_status, request.user, notes)
        except ValueError as exc:
            return Response(
                {'detail': str(exc), 'codigo_error': 'TRANSITION_NOT_ALLOWED'},
                status=400,
            )

        # Re-fetch con select_related/prefetch completo para evitar N+1 al
        # serializar: AdminOrderSerializer accede a items, value, address,
        # shipping_method y user (campos que OrderSerializer/AdminOrderSerializer
        # consumen).
        order = (
            Order.objects
            .select_related('value', 'address', 'shipping_method', 'user')
            .prefetch_related('items')
            .get(pk=order.pk)
        )
        return Response(AdminOrderSerializer(order).data)


class AdminOrderCancelView(APIView):
    """
    POST /api/v1/admin/orders/<order_number>/cancel/
    Cancela una orden como administrador.
    UC-ORD-08 (FR-ORD-08.01).
    H-ADM-005: admin puede cancelar PENDING, PROCESSING, IN_PREPARATION.
    Motivo obligatorio — mínimo 10 caracteres.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'orders.edit'

    @extend_schema(
        summary='Cancelar orden (admin)',
        description=(
            'Cancela una orden con motivo obligatorio. '
            'El admin puede cancelar PENDING, PROCESSING e IN_PREPARATION '
            '(a diferencia del comprador que solo puede PENDING y PROCESSING). '
            'Restaura stock e inicia reembolso si aplica.'
        ),
        request={'application/json': {
            'type': 'object',
            'properties': {
                'reason': {'type': 'string', 'minLength': 10},
            },
            'required': ['reason'],
        }},
        responses={
            200: AdminOrderSerializer,
            400: OpenApiResponse(description='Cancelación no permitida o motivo inválido.'),
            404: OpenApiResponse(description='Orden no encontrada.'),
            503: OpenApiResponse(description='Gateway de reembolso no disponible.'),
        },
        tags=['orders-admin'],
    )
    def post(self, request, order_number):

        try:
            order = (
                Order.objects
                .select_related('value', 'user', 'shipping_method')
                .prefetch_related('items__product', 'items__variant', 'payments')
                .get(order_number=order_number)
            )
        except Order.DoesNotExist:
            return Response(
                {'detail': 'Orden no encontrada.', 'codigo_error': 'ORDER_NOT_FOUND'},
                status=404,
            )

        reason = request.data.get('reason', '').strip()
        try:
            admin_cancel_order(order, reason, request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc), 'codigo_error': 'CANCELLATION_NOT_ALLOWED'},
                status=400,
            )
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc), 'codigo_error': 'GATEWAY_UNAVAILABLE'},
                status=503,
            )

        # Re-fetch con select_related/prefetch completo para evitar N+1 al
        # serializar con AdminOrderSerializer (accede a items, value, address,
        # shipping_method, user).
        order = (
            Order.objects
            .select_related('value', 'address', 'shipping_method', 'user')
            .prefetch_related('items')
            .get(pk=order.pk)
        )
        return Response(AdminOrderSerializer(order).data)


class AdminDashboardView(APIView):
    """
    GET /api/v1/admin/dashboard/
    Dashboard transaccional del administrador.
    UC-ORD-10. Retorna 4 bloques en una sola respuesta.
    H-ADM-004: usa SiteSettings.payment_timeout_minutes para alertas.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'orders.view'

    @extend_schema(
        summary='Dashboard transaccional (admin)',
        description=(
            'Retorna 4 bloques en una sola llamada: '
            '1) contadores de órdenes por estado, '
            '2) alertas de órdenes próximas a expirar (>80% del timeout), '
            '3) resumen del día (pagos aprobados hoy), '
            '4) últimas 10 órdenes.'
        ),
        responses={200: OpenApiResponse(description='Dashboard con 4 bloques.')},
        tags=['orders-admin'],
    )
    def get(self, request):
        data = get_dashboard_data()
        return Response(data)
