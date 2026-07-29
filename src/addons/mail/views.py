"""
Views — addons.mail.

User endpoints (UC-NOT-01..06):
  GET    /api/v1/notifications/                        list
  GET    /api/v1/notifications/unread-count/           unread count
  POST   /api/v1/notifications/{id}/read/              mark one as read
  POST   /api/v1/notifications/read-all/               mark all as read
  GET    /api/v1/notifications/preferences/            list preferences
  PUT    /api/v1/notifications/preferences/            update preferences

Admin endpoints (UC-NOT-07):
  GET    /api/v1/admin/notifications/audience-count/   audience size
  POST   /api/v1/admin/notifications/manual/           send manual

Identifiers + JSON keys in English (DEC-DOC-005).
"""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema, inline_serializer
from rest_framework import fields as rf_fields
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from addons.authz.permissions import HasCapability
from rest_framework.response import Response
from rest_framework.views import APIView
from addons.mail.models import MANDATORY_NOTIFICATION_TYPES, NOTIFICATION_TYPE_LABELS, ManualNotification, Notification, NotificationPreference, NotificationType
from addons.mail.audience import count_audience, resolve_audience_user_ids
from addons.mail.models.manual_fanout import dispatch_manual_fanout
from .serializers import ManualNotificationCreateSerializer, ManualNotificationResponseSerializer, NotificationPreferenceItemSerializer, NotificationPreferencesUpdateSerializer, NotificationSerializer




class _NotificationPagination(PageNumberPagination):
    """H-CICLO88-02: paginar bandeja para evitar respuesta sin limite."""
    page_size             = 50
    page_size_query_param = 'page_size'
    max_page_size         = 200


# Hard cap: ante un admin que envie notificaciones masivas a un usuario
# concreto el endpoint devuelve como maximo este numero de filas.
# Protege al frontend y al worker WSGI frente a bandejas con miles
# de mensajes (UC-NOT-01 DoS via admin manual fanout).
_INBOX_CAP = 500


# ────────────────────────────── UC-NOT-01 ────────────────────────────────
class NotificationListView(APIView):
    """GET /api/v1/notifications/."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.notifications'

    @extend_schema(
        summary='Listar notificaciones del usuario',
        tags=['notifications'],
        parameters=[
            OpenApiParameter('page',      int, description='Numero de pagina.'),
            OpenApiParameter('page_size', int, description='Resultados por pagina (max 200).'),
        ],
        responses=NotificationSerializer(many=True),
    )
    def get(self, request):
        # H-CICLO48-02: order_by('-created_at') garantiza orden determinista.
        # El modelo tiene Meta.ordering=['-created_at'] pero reliar en el
        # ordering de Meta con queryset.filter() puede perderse tras un
        # .values() u otras operaciones de combinacion. Se explicita aqui.
        # H-CICLO88-02: limitar a _INBOX_CAP filas antes de paginar para
        # evitar que un admin que envie notificaciones masivas a un usuario
        # cause OOM al serializar miles de objetos en un solo response.
        qs = (
            Notification.objects
            .filter(user=request.user)
            .order_by('-created_at')[:_INBOX_CAP]
        )
        paginator = _NotificationPagination()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            return paginator.get_paginated_response(
                NotificationSerializer(page, many=True).data
            )
        data = NotificationSerializer(qs, many=True).data
        return Response({'results': data})


# ────────────────────────────── UC-NOT-02 ────────────────────────────────
class NotificationUnreadCountView(APIView):
    """GET /api/v1/notifications/unread-count/."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.notifications'
    serializer_class = NotificationSerializer

    @extend_schema(
        summary='Contar notificaciones no leidas',
        tags=['notifications'],
        responses={200: inline_serializer(
            name='UnreadCountResponse',
            fields={'count': rf_fields.IntegerField()},
        )},
    )
    def get(self, request):
        count = Notification.objects.filter(
            user=request.user, read=False,
        ).count()
        return Response({'count': count})


# ────────────────────────────── UC-NOT-03 ────────────────────────────────
class NotificationMarkReadView(APIView):
    """POST /api/v1/notifications/{id}/read/."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.notifications'
    serializer_class = NotificationSerializer

    @extend_schema(
        summary='[DEPRECATED → PATCH /api/v2/notifications/<pk>/] Marcar notificacion como leida',
        deprecated=True,
        tags=['notifications'],
        responses={200: inline_serializer(
            name='NotificationReadResponse',
            fields={'id': rf_fields.IntegerField(), 'read': rf_fields.BooleanField()},
        )},
    )
    def post(self, request, notification_id):
        notif = get_object_or_404(Notification, pk=notification_id)
        if notif.user_id != request.user.id:
            raise Http404
        if not notif.read:
            notif.read = True
            notif.save(update_fields=['read', 'updated_at'])
        return Response({'id': notif.pk, 'read': True})


# ────────────────────────────── UC-NOT-04 ────────────────────────────────
class NotificationMarkAllReadView(APIView):
    """POST /api/v1/notifications/read-all/."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.notifications'
    serializer_class = NotificationSerializer

    @extend_schema(
        summary='[DEPRECATED → PATCH /api/v2/notifications/] Marcar todas las notificaciones como leidas',
        deprecated=True,
        tags=['notifications'],
        responses={200: inline_serializer(
            name='MarkAllReadResponse',
            fields={'updated': rf_fields.IntegerField()},
        )},
    )
    def post(self, request):
        updated = Notification.objects.filter(
            user=request.user, read=False,
        ).update(read=True, updated_at=timezone.now())
        return Response({'updated': updated})


# ────────────────────────────── UC-NOT-06 ────────────────────────────────
def _build_preference_rows(user):
    """Devuelve una lista de dicts por cada tipo soportado."""
    existing = {
        pref.type: pref
        for pref in NotificationPreference.objects.filter(user=user)
    }
    rows = []
    for type_value, _ in NotificationType.choices:
        is_mandatory = type_value in MANDATORY_NOTIFICATION_TYPES
        if is_mandatory:
            enabled = True
        else:
            pref = existing.get(type_value)
            enabled = pref.enabled if pref is not None else True
        rows.append({
            'type': type_value,
            'enabled': enabled,
            'mandatory': is_mandatory,
            'label': NOTIFICATION_TYPE_LABELS.get(type_value, type_value),
        })
    return rows


def _upsert_preference(user, type_value, enabled):
    """Fija ``enabled`` para (user, type) de forma tolerante a duplicados.

    H-NOT-01: ``update_or_create`` usa ``get()`` internamente y lanza
    ``MultipleObjectsReturned`` -> 500 si existen filas duplicadas de
    (user, type). Eso NO puede pasar mientras la UniqueConstraint
    ``unique_notification_preference`` esté activa (migración 0004), pero un
    entorno con la constraint ausente (drift de esquema) sí las permitiría, y
    entonces el GET tolera el duplicado (colapsa en un dict) mientras el PUT
    revienta — exactamente el síntoma "500 al guardar, pero la página carga".

    Este upsert es robusto sin importar el estado del esquema: colapsa
    cualquier duplicado preexistente a una sola fila coherente.
    """
    qs = NotificationPreference.objects.filter(user=user, type=type_value)
    pref = qs.first()
    if pref is None:
        NotificationPreference.objects.create(
            user=user, type=type_value, enabled=enabled,
        )
        return
    # Colapsa duplicados residuales (si los hubiera) a la fila canónica.
    qs.exclude(pk=pref.pk).delete()
    if pref.enabled != enabled:
        pref.enabled = enabled
        pref.save(update_fields=['enabled'])


class NotificationPreferencesView(APIView):
    """GET/PUT /api/v2/notifications/preferences/."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.notifications'

    @extend_schema(
        summary='Listar preferencias de notificacion',
        tags=['notifications'],
        responses=NotificationPreferenceItemSerializer(many=True),
    )
    def get(self, request):
        rows = _build_preference_rows(request.user)
        return Response({
            'results': NotificationPreferenceItemSerializer(rows, many=True).data,
        })

    @extend_schema(
        summary='Actualizar preferencias de notificacion',
        tags=['notifications'],
        request=NotificationPreferencesUpdateSerializer,
        responses=NotificationPreferenceItemSerializer(many=True),
    )
    def put(self, request):
        serializer = NotificationPreferencesUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        items = serializer.validated_data['preferences']

        skipped_mandatory = []
        with transaction.atomic():
            for item in items:
                type_value = item['type']
                if type_value in MANDATORY_NOTIFICATION_TYPES:
                    if item['enabled'] is False:
                        skipped_mandatory.append(type_value)
                    continue
                _upsert_preference(request.user, type_value, item['enabled'])

        rows = _build_preference_rows(request.user)
        return Response({
            'results': NotificationPreferenceItemSerializer(rows, many=True).data,
            'skipped_mandatory': skipped_mandatory,
        })


# ────────────────────────────── UC-NOT-07 (admin) ────────────────────────
def _compute_audience_count(recipient_type, recipient_identifier, product_id):
    """
    Estima la cantidad de destinatarios para un envio manual.

    USER             -> 1 si el username/email coincide con un usuario activo.
    PRODUCT_BUYERS   -> usuarios distintos que compraron el producto.
    """
    User = get_user_model()
    if recipient_type == ManualNotification.RecipientType.USER:
        if not recipient_identifier:
            return 0
        # Party (T-201): el identificador de usuario es el email (no username).
        return User.objects.filter(
            is_active=True, email=recipient_identifier,
        ).count()

    if recipient_type == ManualNotification.RecipientType.PRODUCT_BUYERS:
        # El público lo resuelve su dueño (``sale``), inscrito en el registro
        # de audiencias — ``mail`` ya no importa ``SaleOrderLine`` (T-035).
        return count_audience(recipient_type, product_id=product_id)

    return 0


def _resolve_audience_user_ids(recipient_type, recipient_identifier, product_id):
    """Devuelve la lista de user_ids destinatarios."""
    User = get_user_model()
    if recipient_type == ManualNotification.RecipientType.USER:
        # Party (T-201): el identificador de usuario es el email (no username).
        qs = User.objects.filter(
            is_active=True, email=recipient_identifier,
        )
        return list(qs.values_list('id', flat=True))

    if recipient_type == ManualNotification.RecipientType.PRODUCT_BUYERS:
        return list(resolve_audience_user_ids(recipient_type, product_id=product_id))

    return []


class AdminAudienceCountView(APIView):
    """GET /api/v1/admin/notifications/audience-count/."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'notifications.view'
    serializer_class = ManualNotificationCreateSerializer

    @extend_schema(
        summary='Tamano de la audiencia destino',
        tags=['notifications'],
        parameters=[
            OpenApiParameter('recipient_type', str, required=True),
            OpenApiParameter('recipient_identifier', str, required=False),
            OpenApiParameter('product_id', int, required=False),
        ],
        responses={200: inline_serializer(
            name='AudienceCountResponse',
            fields={'count': rf_fields.IntegerField()},
        )},
    )
    def get(self, request):
        params = request.query_params
        recipient_type = params.get('recipient_type', '')
        recipient_identifier = params.get('recipient_identifier', '')
        product_id_raw = params.get('product_id')

        valid_types = {
            ManualNotification.RecipientType.USER,
            ManualNotification.RecipientType.PRODUCT_BUYERS,
        }
        if recipient_type not in valid_types:
            return Response(
                {'codigo_error': 'INVALID_RECIPIENT_TYPE',
                 'detail': 'recipient_type invalido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product_id = None
        if product_id_raw:
            try:
                product_id = int(product_id_raw)
            except (TypeError, ValueError):
                return Response(
                    {'codigo_error': 'INVALID_PRODUCT_ID',
                     'detail': 'product_id debe ser entero.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        count = _compute_audience_count(
            recipient_type, recipient_identifier, product_id,
        )
        return Response({'count': count})


class AdminManualNotificationCreateView(APIView):
    """POST /api/v1/admin/notifications/manual/."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'notifications.create'

    @extend_schema(
        summary='Enviar notificacion manual',
        tags=['notifications'],
        request=ManualNotificationCreateSerializer,
        responses={201: ManualNotificationResponseSerializer},
    )
    def post(self, request):
        serializer = ManualNotificationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        recipient_type = payload['recipient_type']
        recipient_identifier = payload.get('recipient_identifier', '')
        product_id = payload.get('product_id')
        subject = payload['subject']
        message = payload['message']

        user_ids = _resolve_audience_user_ids(
            recipient_type, recipient_identifier, product_id,
        )

        with transaction.atomic():
            manual = ManualNotification.objects.create(
                sender=request.user,
                recipient_type=recipient_type,
                recipient_identifier=recipient_identifier or '',
                product_id=product_id,
                subject=subject,
                message=message,
                recipients_count=len(user_ids),
                status=(
                    ManualNotification.Status.SENT
                    if user_ids else ManualNotification.Status.FAILED
                ),
            )

            if user_ids:
                # H-CICLO18-05: dispatch_manual_fanout es una funcion plana
                # (sin Celery, cnst-arquitectura T6). Llamar .delay() sobre
                # una funcion sin decorador @shared_task lanza AttributeError
                # para audiencias > MANUAL_FANOUT_ASYNC_THRESHOLD. Se elimina
                # la bifurcacion sync/async — siempre se llama directamente.
                dispatch_manual_fanout(
                    list(user_ids),
                    subject,
                    message,
                    NotificationType.PROMOTION,
                )

        return Response(
            ManualNotificationResponseSerializer(manual).data,
            status=status.HTTP_201_CREATED,
        )


class NotificationListV2View(NotificationListView):
    """
    GET  /api/v2/notifications/ — list (same as v1).
    PATCH /api/v2/notifications/ — bulk mark all unread as read.

    Combines both operations at the canonical resource URL instead
    of a verb-based /read-all/ sub-path.
    """

    @extend_schema(
        summary='Marcar todas las notificaciones como leidas (PATCH)',
        tags=['notifications'],
        request=None,
        responses={200: inline_serializer(
            name='BulkMarkReadResponse',
            fields={'updated': rf_fields.IntegerField()},
        )},
    )
    def patch(self, request):
        updated = Notification.objects.filter(
            user=request.user, read=False,
        ).update(read=True, updated_at=timezone.now())
        return Response({'updated': updated})


class NotificationMarkReadV2View(APIView):
    """
    PATCH /api/v2/notifications/<pk>/ — mark one notification as read.

    Replaces POST /api/v1/notifications/<id>/read/ with an idempotent
    PATCH at the resource URL. Accepts {read: true} body (ignored when
    absent — always marks as read for backwards compat with v1 semantics).
    """

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.notifications'

    @extend_schema(
        summary='Marcar notificacion como leida (PATCH)',
        tags=['notifications'],
        request=inline_serializer(
            name='NotificationMarkReadRequest',
            fields={'read': rf_fields.BooleanField(required=False, default=True)},
        ),
        responses={200: inline_serializer(
            name='NotificationMarkReadResponse',
            fields={
                'id': rf_fields.IntegerField(),
                'read': rf_fields.BooleanField(),
            },
        )},
    )
    def patch(self, request, pk):
        notif = get_object_or_404(Notification, pk=pk)
        if notif.user_id != request.user.id:
            raise Http404
        if not notif.read:
            notif.read = True
            notif.save(update_fields=['read', 'updated_at'])
        return Response({'id': notif.pk, 'read': True})
