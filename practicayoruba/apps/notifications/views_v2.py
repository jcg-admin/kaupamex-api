"""
Views v2 — apps.notifications (F2 Tier B).

PATCH /api/v2/notifications/       — bulk mark all unread as read
PATCH /api/v2/notifications/<pk>/  — mark one notification as read

v1 used POST + verb-based URLs (read-all, <id>/read/).
v2 uses PATCH at the resource URL, which is idempotent and REST-canonical.
"""
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import fields as rf_fields
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .views import NotificationListView


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

    permission_classes = [IsAuthenticated]

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
