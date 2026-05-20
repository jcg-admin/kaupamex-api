"""
Views — apps.notifications.

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
from django.conf import settings as dj_settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from apps.orders.models import OrderItem
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import MANDATORY_NOTIFICATION_TYPES, NOTIFICATION_TYPE_LABELS, ManualNotification, Notification, NotificationPreference, NotificationType
from .tasks import dispatch_manual_fanout
from .serializers import ManualNotificationCreateSerializer, ManualNotificationResponseSerializer, NotificationPreferenceItemSerializer, NotificationPreferencesUpdateSerializer, NotificationSerializer




# ────────────────────────────── UC-NOT-01 ────────────────────────────────
class NotificationListView(APIView):
    """GET /api/v1/notifications/."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Listar notificaciones del usuario',
        tags=['notifications'],
        responses=NotificationSerializer(many=True),
    )
    def get(self, request):
        qs = Notification.objects.filter(user=request.user)
        data = NotificationSerializer(qs, many=True).data
        return Response({'results': data})


# ────────────────────────────── UC-NOT-02 ────────────────────────────────
class NotificationUnreadCountView(APIView):
    """GET /api/v1/notifications/unread-count/."""

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    @extend_schema(
        summary='Contar notificaciones no leidas',
        tags=['notifications'],
    )
    def get(self, request):
        count = Notification.objects.filter(
            user=request.user, read=False,
        ).count()
        return Response({'count': count})


# ────────────────────────────── UC-NOT-03 ────────────────────────────────
class NotificationMarkReadView(APIView):
    """POST /api/v1/notifications/{id}/read/."""

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    @extend_schema(
        summary='Marcar notificacion como leida',
        tags=['notifications'],
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

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    @extend_schema(
        summary='Marcar todas las notificaciones como leidas',
        tags=['notifications'],
    )
    def post(self, request):
        updated = Notification.objects.filter(
            user=request.user, read=False,
        ).update(read=True)
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


class NotificationPreferencesView(APIView):
    """GET/PUT /api/v1/notifications/preferences/."""

    permission_classes = [IsAuthenticated]

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

        with transaction.atomic():
            for item in items:
                type_value = item['type']
                if type_value in MANDATORY_NOTIFICATION_TYPES:
                    # Los mandatory no se pueden deshabilitar; se ignoran.
                    continue
                NotificationPreference.objects.update_or_create(
                    user=request.user,
                    type=type_value,
                    defaults={'enabled': item['enabled']},
                )

        rows = _build_preference_rows(request.user)
        return Response({
            'results': NotificationPreferenceItemSerializer(rows, many=True).data,
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
        return User.objects.filter(
            is_active=True,
        ).filter(
            username=recipient_identifier,
        ).count() or User.objects.filter(
            is_active=True, email=recipient_identifier,
        ).count()

    if recipient_type == ManualNotification.RecipientType.PRODUCT_BUYERS:
        if not product_id:
            return 0
        return (
            OrderItem.objects
            .filter(product_id=product_id, order__user__isnull=False)
            .values('order__user_id')
            .distinct()
            .count()
        )

    return 0


def _resolve_audience_user_ids(recipient_type, recipient_identifier, product_id):
    """Devuelve la lista de user_ids destinatarios."""
    User = get_user_model()
    if recipient_type == ManualNotification.RecipientType.USER:
        qs = User.objects.filter(is_active=True).filter(
            username=recipient_identifier,
        )
        if not qs.exists():
            qs = User.objects.filter(
                is_active=True, email=recipient_identifier,
            )
        return list(qs.values_list('id', flat=True))

    if recipient_type == ManualNotification.RecipientType.PRODUCT_BUYERS:
        return list(
            OrderItem.objects
            .filter(product_id=product_id, order__user__isnull=False)
            .values_list('order__user_id', flat=True)
            .distinct()
        )

    return []


class AdminAudienceCountView(APIView):
    """GET /api/v1/admin/notifications/audience-count/."""

    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = ManualNotificationCreateSerializer

    @extend_schema(
        summary='Tamano de la audiencia destino',
        tags=['notifications'],
        parameters=[
            OpenApiParameter('recipient_type', str, required=True),
            OpenApiParameter('recipient_identifier', str, required=False),
            OpenApiParameter('product_id', int, required=False),
        ],
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
                {'error_code': 'INVALID_RECIPIENT_TYPE',
                 'detail': 'recipient_type invalido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product_id = None
        if product_id_raw:
            try:
                product_id = int(product_id_raw)
            except (TypeError, ValueError):
                return Response(
                    {'error_code': 'INVALID_PRODUCT_ID',
                     'detail': 'product_id debe ser entero.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        count = _compute_audience_count(
            recipient_type, recipient_identifier, product_id,
        )
        return Response({'count': count})


class AdminManualNotificationCreateView(APIView):
    """POST /api/v1/admin/notifications/manual/."""

    permission_classes = [IsAuthenticated, IsAdminUser]

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

            # D-004: fanout sincrono para audiencias chicas (preserva el
            # comportamiento previo, mantiene los tests existentes verdes
            # y evita la latencia de despachar a Celery para 1-N usuarios).
            # Para audiencias grandes (>threshold) se despacha al broker
            # para no bloquear la request. En tests, el override
            # CELERY_TASK_ALWAYS_EAGER=True hace que .delay() ejecute en
            # proceso, eliminando la dependencia de redis.
            threshold = getattr(
                dj_settings, 'MANUAL_FANOUT_ASYNC_THRESHOLD', 100,
            )
            if user_ids:
                if len(user_ids) > threshold:
                    dispatch_manual_fanout.delay(
                        list(user_ids),
                        subject,
                        message,
                        NotificationType.PROMOTION,
                    )
                else:
                    # Camino sincrono (logica original conservada).
                    disabled = set(
                        NotificationPreference.objects
                        .filter(
                            user_id__in=user_ids,
                            type=NotificationType.PROMOTION,
                            enabled=False,
                        )
                        .values_list('user_id', flat=True)
                    )
                    to_create = [
                        Notification(
                            user_id=uid,
                            type=NotificationType.PROMOTION,
                            subject=subject,
                            body=message,
                        )
                        for uid in user_ids
                        if uid not in disabled
                    ]
                    if to_create:
                        Notification.objects.bulk_create(to_create)

        return Response(
            ManualNotificationResponseSerializer(manual).data,
            status=status.HTTP_201_CREATED,
        )
