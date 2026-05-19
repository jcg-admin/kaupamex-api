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
"""
from datetime import timedelta

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SupportTicket, SupportTicketReply
from .serializers import (
    SupportTicketCloseSerializer,
    SupportTicketCreateResponseSerializer,
    SupportTicketCreateSerializer,
    SupportTicketDetailSerializer,
    SupportTicketListSerializer,
    SupportTicketReplyCreateSerializer,
    SupportTicketReplySerializer,
)

HIGH_PRIORITY_CATEGORIES = {
    SupportTicket.Category.URGENT,
    SupportTicket.Category.FRAUD,
}

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
    """
    qs = SupportTicket.objects.all()
    ticket = get_object_or_404(qs, pk=ticket_id)
    if not user.is_staff and ticket.user_id != user.id:
        raise Http404
    return ticket


# ────────────────────────────── UC-SUPP-01 / UC-SUPP-02 ──────────────────
class SupportTicketListCreateView(APIView):
    """POST crear ticket / GET listar tickets propios del comprador."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Listar mis tickets de soporte',
        tags=['support'],
        responses=SupportTicketListSerializer(many=True),
    )
    def get(self, request):
        qs = SupportTicket.objects.filter(user=request.user)
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
                    'error_code': 'DUPLICATE_TICKET',
                    'detail':     'Ya tienes un ticket abierto con esta categoria.',
                    'ticket_id':  existing.pk,
                },
                status=status.HTTP_409_CONFLICT,
            )

        ticket = SupportTicket.objects.create(
            user=request.user,
            subject=payload['subject'],
            body=payload['body'],
            category=category,
            priority=priority,
            order_id=payload.get('order_id'),
        )
        return Response(
            SupportTicketCreateResponseSerializer(ticket).data,
            status=status.HTTP_201_CREATED,
        )


class SupportTicketDetailView(APIView):
    """GET detalle del ticket propio (o cualquiera si is_staff)."""

    permission_classes = [IsAuthenticated]

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


# ────────────────────────────── UC-SUPP-03 ───────────────────────────────
class SupportTicketReplyView(APIView):
    """POST /api/v1/support/tickets/{id}/replies/."""

    permission_classes = [IsAuthenticated]

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
        if is_internal and not request.user.is_staff:
            raise PermissionDenied('Solo staff puede crear notas internas.')

        if ticket.status == SupportTicket.Status.CLOSED:
            return Response(
                {'error_code': 'TICKET_CLOSED',
                 'detail': 'No se puede responder un ticket cerrado.'},
                status=status.HTTP_409_CONFLICT,
            )

        reply = SupportTicketReply.objects.create(
            ticket=ticket,
            author=request.user,
            body=payload['body'],
            is_internal_note=is_internal,
        )

        if not is_internal:
            if request.user.is_staff:
                ticket.status = SupportTicket.Status.AWAITING_USER
            else:
                ticket.status = SupportTicket.Status.IN_PROGRESS
            ticket.save(update_fields=['status', 'updated_at'])

        return Response(
            SupportTicketReplySerializer(reply).data,
            status=status.HTTP_201_CREATED,
        )


# ────────────────────────────── UC-SUPP-04 ───────────────────────────────
class SupportTicketCloseView(APIView):
    """POST /api/v1/support/tickets/{id}/close/."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Cerrar ticket',
        tags=['support'],
        request=SupportTicketCloseSerializer,
    )
    def post(self, request, ticket_id):
        ticket = _get_ticket_for_user(ticket_id, request.user)
        if ticket.status == SupportTicket.Status.CLOSED:
            return Response(
                {'error_code': 'TICKET_ALREADY_CLOSED',
                 'detail': 'El ticket ya esta cerrado.'},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = SupportTicketCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get('reason') or ''

        ticket.status = SupportTicket.Status.CLOSED
        ticket.save(update_fields=['status', 'updated_at'])

        body = reason or (
            'El staff cerro este ticket.' if request.user.is_staff
            else 'El comprador marco este ticket como resuelto.'
        )
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
            'closed_by': 'ADMIN' if request.user.is_staff else 'BUYER',
        })


class SupportTicketReopenView(APIView):
    """POST /api/v1/support/tickets/{id}/reopen/."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Reabrir ticket',
        tags=['support'],
    )
    def post(self, request, ticket_id):
        ticket = _get_ticket_for_user(ticket_id, request.user)
        if ticket.status != SupportTicket.Status.CLOSED:
            return Response(
                {'error_code': 'TICKET_NOT_CLOSED',
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


# ────────────────────────────── UC-SUPP-05 ───────────────────────────────
class AdminSupportTicketListView(ListAPIView):
    """GET /api/v1/admin/support/tickets/ — admin queue."""

    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = SupportTicketListSerializer

    @extend_schema(
        summary='Bandeja de tickets (admin)',
        tags=['support'],
        parameters=[
            OpenApiParameter('status', str, required=False),
            OpenApiParameter('priority', str, required=False),
            OpenApiParameter('category', str, required=False),
            OpenApiParameter('created_from', str, required=False),
            OpenApiParameter('created_to', str, required=False),
            OpenApiParameter('assigned_to', int, required=False),
        ],
    )
    def get_queryset(self):
        qs = SupportTicket.objects.all()
        params = self.request.query_params
        if params.get('status'):
            qs = qs.filter(status=params['status'])
        if params.get('priority'):
            qs = qs.filter(priority=params['priority'])
        if params.get('category'):
            qs = qs.filter(category=params['category'])
        if params.get('created_from'):
            qs = qs.filter(created_at__gte=params['created_from'])
        if params.get('created_to'):
            qs = qs.filter(created_at__lte=params['created_to'])
        if params.get('assigned_to'):
            qs = qs.filter(user_id=params['assigned_to'])
        return qs
