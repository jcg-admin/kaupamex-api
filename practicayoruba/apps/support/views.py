"""
Views — apps.support (UC-SUPP-01..05).

User endpoints:
  POST   /api/v1/support/tickets/                 UC-SUPP-01 create
  GET    /api/v1/support/tickets/                 UC-SUPP-02 list user tickets
  GET    /api/v1/support/tickets/{id}/            UC-SUPP-02 detail
  POST   /api/v1/support/tickets/{id}/replies/    UC-SUPP-03 add reply
  POST   /api/v1/support/tickets/{id}/close/      UC-SUPP-04 close
  POST   /api/v1/support/tickets/{id}/reopen/     UC-SUPP-04 reopen

Admin endpoints:
  GET    /api/v1/admin/support/tickets/           UC-SUPP-05 queue
  GET    /api/v1/admin/support/tickets/export/    UC-SUPP-05 CSV export
"""
import csv
import io
from datetime import timedelta
from django.db import transaction
from django.db.models import (
    Avg, Count, DurationField, ExpressionWrapper, F, OuterRef, Q, Subquery,
)
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from rest_framework import fields as rf_fields
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from apps.authz.permissions import HasCapability
from apps.authz.services import SUPERADMIN_ROLE_CODE, is_superadmin
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.notifications.service import notify_support_created
from apps.orders.models import Order
from .models import SupportTicket, SupportTicketReply
from .serializers import AdminSupportTicketListSerializer, SupportTicketCloseSerializer, SupportTicketCreateResponseSerializer, SupportTicketCreateSerializer, SupportTicketDetailSerializer, SupportTicketListSerializer, SupportTicketReplyCreateSerializer, SupportTicketReplySerializer



HIGH_PRIORITY_CATEGORIES = {
    SupportTicket.Category.URGENT,
    SupportTicket.Category.FRAUD,
}


class _AdminTicketPagination(PageNumberPagination):
    """H-CICLO89-01: paginacion para la cola admin de tickets de soporte.
    Sin paginacion, la vista cargaba todos los tickets en memoria con
    list(qs), lo que produce OOM en instancias con muchos tickets.
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class _BuyerTicketPagination(PageNumberPagination):
    """H-CICLO117-02: paginacion para el listado de tickets del comprador.
    Sin paginacion, SupportTicketListCreateView.get() serializaba todos
    los tickets del usuario en una sola respuesta; usuarios con muchos
    tickets producian respuestas lentas y consumo de memoria innecesario.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

# UC-SUPP-01 AC-03: ventana de deteccion de tickets duplicados. Si el
# comprador ya tiene un ticket abierto con la misma categoria + orden
# en los ultimos 1440 minutos (24h), el nuevo POST se rechaza con
# 409 DUPLICATE_TICKET para protegerse contra dobles envios del UI o
# bots de soporte.
DUPLICATE_TICKET_WINDOW = timedelta(hours=24)
ACTIVE_TICKET_STATUSES = (
    SupportTicket.Status.OPEN,
    SupportTicket.Status.IN_PROGRESS,
    SupportTicket.Status.AWAITING_USER,
)


def _get_ticket_for_user(ticket_id, user):
    """
    Devuelve el ticket si pertenece al user o si el user es staff.
    Si no existe o pertenece a otro comprador -> Http404
    (RNF-SEC-003: no revelar la existencia del ticket).

    H-CICLO18-03: select_related('user') + prefetch_related('replies__author')
    previenen N+1 queries al serializar el hilo de conversacion y el campo
    buyer (SupportTicketDetailSerializer).
    """
    qs = SupportTicket.objects.select_related('user').prefetch_related(
        'replies__author'
    )
    ticket = get_object_or_404(qs, pk=ticket_id)
    if not is_superadmin(user) and ticket.user_id != user.id:
        raise Http404
    return ticket


def _annotate_first_response(qs):
    """Anota ``first_response_at``: created_at de la primera respuesta de
    staff no interna de cada ticket. UC-SUPP-05 (T-009) — metrica de
    tiempo-medio-de-primera-respuesta y columna de export CSV.

    Una nota interna (``is_internal_note=True``) o una respuesta del propio
    comprador no cuentan como primera respuesta: la metrica mide cuanto
    tarda el equipo de soporte en contestarle al comprador.
    """
    # Party/authz (T-201): "staff reply" = respuesta cuyo autor tiene el rol
    # superadmin (no hay is_staff nativo).
    first_staff_reply_qs = (
        SupportTicketReply.objects
        .filter(
            ticket=OuterRef('pk'),
            author__role_assignments__role__code=SUPERADMIN_ROLE_CODE,
            is_internal_note=False,
        )
        .order_by('created_at')
        .values('created_at')[:1]
    )
    return qs.annotate(first_response_at=Subquery(first_staff_reply_qs))


def _apply_admin_filters(qs, params):
    """Aplica los filtros de la cola admin de tickets (UC-SUPP-05) sobre
    ``qs``. Compartido entre ``AdminSupportTicketListView`` (JSON paginado)
    y ``AdminSupportTicketExportCSVView`` (CSV completo) para que ambos
    endpoints filtren exactamente igual.

    Devuelve ``(queryset, None)`` o ``(None, Response)`` si el filtro de
    status es invalido.
    """
    if params.get('status'):
        valid_statuses = {s.value for s in SupportTicket.Status}
        if params['status'] not in valid_statuses:
            return None, Response(
                {
                    'detail': f"Status inválido: '{params['status']}'.",
                    'codigo_error': 'INVALID_STATUS',
                    'valores_validos': sorted(valid_statuses),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = qs.filter(status=params['status'])
    if params.get('priority'):
        qs = qs.filter(priority=params['priority'])
    if params.get('category'):
        qs = qs.filter(category=params['category'])
    if params.get('created_from'):
        qs = qs.filter(created_at__gte=params['created_from'])
    if params.get('created_to'):
        qs = qs.filter(created_at__lte=params['created_to'])
    # H-CICLO23-04: `user_id` filtra por el comprador propietario del ticket.
    if params.get('user_id'):
        qs = qs.filter(user_id=params['user_id'])
    q = (params.get('q') or '').strip()
    if q:
        qs = qs.filter(
            Q(user__email__icontains=q) | Q(subject__icontains=q)
        )
    return qs, None


# ────────────────────────────── UC-SUPP-01 / UC-SUPP-02 ──────────────────
class SupportTicketListCreateView(APIView):
    """POST crear ticket / GET listar tickets propios del comprador."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.support'

    @extend_schema(
        summary='Listar mis tickets de soporte',
        tags=['support'],
        responses=SupportTicketListSerializer(many=True),
    )
    def get(self, request):
        # H-CICLO48-01: order_by evita resultados no deterministos entre
        # paginas. Sin el ordering el DB puede retornar el mismo ticket en
        # pagina 1 y pagina 2 si el plan de ejecucion cambia entre requests.
        # H-CICLO117-02: paginar el listado para evitar serializar todos
        # los tickets en memoria. Sin paginacion, compradores con muchos
        # tickets producian respuestas lentas y alto consumo de RAM.
        qs = SupportTicket.objects.filter(user=request.user).order_by('-created_at')
        paginator = _BuyerTicketPagination()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            return paginator.get_paginated_response(
                SupportTicketListSerializer(page, many=True).data
            )
        return Response(SupportTicketListSerializer(qs, many=True).data)

    @extend_schema(
        summary='Crear ticket de soporte',
        tags=['support'],
        request=SupportTicketCreateSerializer,
        responses={201: SupportTicketCreateResponseSerializer},
    )
    def post(self, request):
        serializer = SupportTicketCreateSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        # H-18: la UI solo conoce order_number (el PK no se expone en la lista de
        # ordenes). Se resuelve aqui al order_id del comprador, con el mismo
        # aislamiento y clave de error escalar que el resto de la vista
        # (RNF-SEC-003: mismo error si no existe o es ajena).
        order_number = (payload.pop('order_number', None) or '').strip()
        if order_number and not payload.get('order_id'):
            order = Order.objects.filter(
                order_number=order_number, user=request.user,
            ).only('pk').first()
            if order is None:
                return Response(
                    {
                        'codigo_error': 'ORDER_NOT_FOUND',
                        'detail':     'La orden no existe o no pertenece al comprador.',
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            payload['order_id'] = order.pk

        category = payload.get('category', SupportTicket.Category.GENERAL)
        priority = payload.get('priority', SupportTicket.Priority.NORMAL)
        if category in HIGH_PRIORITY_CATEGORIES:
            priority = SupportTicket.Priority.HIGH

        # UC-SUPP-01 AC-03 — duplicate ticket detection (D-003).
        threshold = timezone.now() - DUPLICATE_TICKET_WINDOW
        duplicate_qs = SupportTicket.objects.filter(
            user=request.user,
            category=category,
            status__in=ACTIVE_TICKET_STATUSES,
            created_at__gte=threshold,
        )
        if payload.get('order_id'):
            duplicate_qs = duplicate_qs.filter(order_id=payload['order_id'])
        else:
            duplicate_qs = duplicate_qs.filter(order_id__isnull=True)
        existing = duplicate_qs.order_by('-created_at').first()
        if existing is not None:
            return Response(
                {
                    'codigo_error': 'DUPLICATE_TICKET',
                    'detail':     'Ya tienes un ticket abierto con esta categoria.',
                    'ticket_id':  existing.pk,
                },
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            ticket = SupportTicket.objects.create(
                user=request.user,
                subject=payload['subject'],
                body=payload['body'],
                category=category,
                priority=priority,
                order_id=payload.get('order_id'),
            )
            # H-18: confirmar al comprador (in-app + email on_commit). Antes la
            # creacion no notificaba nada, contra UC-SUPP-01 POST-02/7.2.
            notify_support_created(ticket, request.user)

        return Response(
            SupportTicketCreateResponseSerializer(ticket).data,
            status=status.HTTP_201_CREATED,
        )


class SupportTicketDetailView(APIView):
    """GET detalle del ticket propio (o cualquiera si is_staff)."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.support'

    @extend_schema(
        summary='Detalle de ticket',
        tags=['support'],
        responses=SupportTicketDetailSerializer,
    )
    def get(self, request, ticket_id):
        ticket = _get_ticket_for_user(ticket_id, request.user)
        return Response(
            SupportTicketDetailSerializer(
                ticket, context={'request': request}
            ).data
        )


# ────────────────────────────── UC-SUPP-03 ───────────────────────────────────────
class SupportTicketReplyView(APIView):
    """POST /api/v1/support/tickets/{id}/replies/."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.support'

    @extend_schema(
        summary='Responder ticket',
        tags=['support'],
        request=SupportTicketReplyCreateSerializer,
        responses={201: SupportTicketReplySerializer},
    )
    def post(self, request, ticket_id):
        ticket = _get_ticket_for_user(ticket_id, request.user)
        serializer = SupportTicketReplyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        is_internal = payload.get('is_internal_note', False)
        if is_internal and not is_superadmin(request.user):
            raise PermissionDenied('Solo staff puede crear notas internas.')

        if ticket.status == SupportTicket.Status.CLOSED:
            return Response(
                {'codigo_error': 'TICKET_CLOSED',
                 'detail': 'No se puede responder un ticket cerrado.'},
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            reply = SupportTicketReply.objects.create(
                ticket=ticket,
                author=request.user,
                body=payload['body'],
                is_internal_note=is_internal,
            )

            if not is_internal:
                if is_superadmin(request.user):
                    ticket.status = SupportTicket.Status.AWAITING_USER
                else:
                    ticket.status = SupportTicket.Status.IN_PROGRESS
                ticket.save(update_fields=['status', 'updated_at'])

        return Response(
            SupportTicketReplySerializer(reply).data,
            status=status.HTTP_201_CREATED,
        )


# ────────────────────────────── UC-SUPP-04 ───────────────────────────────────────
class SupportTicketCloseView(APIView):
    """POST /api/v1/support/tickets/{id}/close/."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.support'
    serializer_class = SupportTicketCloseSerializer

    @extend_schema(
        summary='[DEPRECATED → PATCH /api/v2/support/tickets/<id>/status/] Cerrar ticket',
        deprecated=True,
        tags=['support'],
        request=SupportTicketCloseSerializer,
        responses={
            200: inline_serializer(
                name='TicketCloseResponse',
                fields={
                    'ticket_id': rf_fields.IntegerField(),
                    'status': rf_fields.CharField(),
                    'closed_at': rf_fields.DateTimeField(),
                    'closed_by': rf_fields.CharField(),
                },
            ),
            409: None,
        },
    )
    def post(self, request, ticket_id):
        ticket = _get_ticket_for_user(ticket_id, request.user)
        if ticket.status == SupportTicket.Status.CLOSED:
            return Response(
                {'codigo_error': 'TICKET_ALREADY_CLOSED',
                 'detail': 'El ticket ya esta cerrado.'},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = SupportTicketCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get('reason') or ''

        body = reason or (
            'El staff cerro este ticket.' if is_superadmin(request.user)
            else 'El comprador marco este ticket como resuelto.'
        )
        with transaction.atomic():
            ticket.status = SupportTicket.Status.CLOSED
            ticket.save(update_fields=['status', 'updated_at'])

            SupportTicketReply.objects.create(
                ticket=ticket,
                author=request.user,
                body=body,
                is_internal_note=False,
            )

        return Response({
            'ticket_id': ticket.pk,
            'status': ticket.status,
            'closed_at': ticket.updated_at,
            'closed_by': 'ADMIN' if is_superadmin(request.user) else 'BUYER',
        })


class SupportTicketReopenView(APIView):
    """POST /api/v1/support/tickets/{id}/reopen/."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.support'
    serializer_class = SupportTicketDetailSerializer

    @extend_schema(
        summary='[DEPRECATED → PATCH /api/v2/support/tickets/<id>/status/] Reabrir ticket',
        deprecated=True,
        tags=['support'],
        responses={
            200: inline_serializer(
                name='TicketReopenResponse',
                fields={
                    'ticket_id': rf_fields.IntegerField(),
                    'status': rf_fields.CharField(),
                    'reopened_at': rf_fields.DateTimeField(),
                },
            ),
            409: None,
        },
    )
    def post(self, request, ticket_id):
        # H-CICLO111-02: envolver en transaction.atomic() para serializar
        # reaperturas concurrentes del mismo ticket. Sin atomic, dos requests
        # simultáneos pasan el chequeo status==CLOSED y ambos ejecutan el
        # save(), produciendo doble transición y potencial estado inconsistente.
        with transaction.atomic():
            ticket = SupportTicket.objects.select_for_update().filter(
                pk=ticket_id
            ).select_related('user').first()
            if ticket is None or (not is_superadmin(request.user) and ticket.user_id != request.user.id):
                raise Http404
            if ticket.status != SupportTicket.Status.CLOSED:
                return Response(
                    {'codigo_error': 'TICKET_NOT_CLOSED',
                     'detail': 'Solo se pueden reabrir tickets cerrados.'},
                    status=status.HTTP_409_CONFLICT,
                )
            ticket.status = SupportTicket.Status.OPEN
            ticket.save(update_fields=['status', 'updated_at'])
        return Response({
            'ticket_id': ticket.pk,
            'status': ticket.status,
            'reopened_at': ticket.updated_at,
        })


# ────────────────────────────── UC-SUPP-05 ─────────────────────────────────────────
class AdminSupportTicketListView(APIView):
    """GET /api/v1/admin/support/tickets/ — admin queue."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'support.manage'

    @extend_schema(
        summary='Bandeja de tickets (admin)',
        tags=['support'],
        parameters=[
            OpenApiParameter('status', str, required=False),
            OpenApiParameter('priority', str, required=False),
            OpenApiParameter('category', str, required=False),
            OpenApiParameter('created_from', str, required=False),
            OpenApiParameter('created_to', str, required=False),
            OpenApiParameter('user_id', int, required=False, description='Filtrar por ID del comprador propietario del ticket'),
            OpenApiParameter('q', str, required=False, description='Search by email/subject'),
        ],
        responses={200: AdminSupportTicketListSerializer(many=True)},
    )
    def get(self, request):
        qs = SupportTicket.objects.all().annotate(replies_count=Count('replies'))
        qs, error = _apply_admin_filters(qs, request.query_params)
        if error is not None:
            return error
        qs = qs.select_related('user').order_by('created_at')

        # Metrics (global, not filtered)
        all_tickets = SupportTicket.objects.all()
        # T-009 (SUPP-05): tiempo-medio-de-primera-respuesta. Promedio, via
        # agregacion de Django (Avg sobre una expresion de duracion), del
        # tiempo entre la apertura del ticket y su primera respuesta de staff
        # no interna. Tickets sin ninguna respuesta de staff se excluyen del
        # promedio (first_response_at es NULL para ellos).
        avg_first_response = (
            _annotate_first_response(all_tickets)
            .filter(first_response_at__isnull=False)
            .annotate(
                response_time=ExpressionWrapper(
                    F('first_response_at') - F('created_at'),
                    output_field=DurationField(),
                )
            )
            .aggregate(avg=Avg('response_time'))['avg']
        )
        metrics = {
            'open':           all_tickets.filter(status='OPEN').count(),
            'in_progress':    all_tickets.filter(status='IN_PROGRESS').count(),
            'awaiting_user':  all_tickets.filter(status='AWAITING_USER').count(),
            'resolved':       all_tickets.filter(status='RESOLVED').count(),
            'closed':         all_tickets.filter(status='CLOSED').count(),
            'avg_first_response_minutes': (
                round(avg_first_response.total_seconds() / 60, 2)
                if avg_first_response is not None else None
            ),
        }

        # H-CICLO89-01: paginar la cola admin para evitar OOM en instalaciones
        # con muchos tickets. El `list(qs)` anterior cargaba todos los tickets
        # en memoria en una sola respuesta.
        paginator = _AdminTicketPagination()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            data = AdminSupportTicketListSerializer(page, many=True).data
            paginated = paginator.get_paginated_response(data)
            paginated.data['metrics'] = metrics
            return paginated

        items = list(qs)
        return Response({
            'count': len(items),
            'results': AdminSupportTicketListSerializer(items, many=True).data,
            'metrics': metrics,
        })


class AdminSupportTicketExportCSVView(APIView):
    """GET /api/v1/admin/support/tickets/export/ — export CSV. T-009 (SUPP-05).

    Exporta la cola completa de tickets (mismos filtros que
    ``AdminSupportTicketListView``, sin paginar) como ``text/csv``. Antes de
    este commit no existia ningun export en support (``grep csv`` = 0).
    """

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'support.manage'

    @extend_schema(
        summary='Exportar tickets de soporte a CSV (admin)',
        tags=['support'],
        parameters=[
            OpenApiParameter('status', str, required=False),
            OpenApiParameter('priority', str, required=False),
            OpenApiParameter('category', str, required=False),
            OpenApiParameter('created_from', str, required=False),
            OpenApiParameter('created_to', str, required=False),
            OpenApiParameter('user_id', int, required=False, description='Filtrar por ID del comprador propietario del ticket'),
            OpenApiParameter('q', str, required=False, description='Search by email/subject'),
        ],
    )
    def get(self, request):
        qs = SupportTicket.objects.all()
        qs, error = _apply_admin_filters(qs, request.query_params)
        if error is not None:
            return error
        qs = _annotate_first_response(qs).select_related('user').order_by(
            'created_at'
        )

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            'id', 'asunto', 'estado', 'prioridad', 'categoria',
            'comprador_email', 'created_at', 'primera_respuesta',
        ])
        for ticket in qs:
            writer.writerow([
                ticket.pk,
                ticket.subject,
                ticket.status,
                ticket.priority,
                ticket.category,
                ticket.user.email if ticket.user_id else '',
                ticket.created_at.isoformat(),
                ticket.first_response_at.isoformat()
                if ticket.first_response_at else '',
            ])

        response = HttpResponse(buf.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = (
            'attachment; filename="support_tickets.csv"'
        )
        return response


class SupportTicketStatusV2View(APIView):
    """PATCH /api/v2/support/tickets/<id>/status/ — Tier B."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.support'

    def patch(self, request, ticket_id):
        action = (request.data.get('action') or '').strip()
        if action == 'close':
            return SupportTicketCloseView().post(request, ticket_id)
        if action == 'reopen':
            return SupportTicketReopenView().post(request, ticket_id)
        return Response(
            {
                'detail': "action debe ser 'close' o 'reopen'.",
                'codigo_error': 'INVALID_ACTION',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
