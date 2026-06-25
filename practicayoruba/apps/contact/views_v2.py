"""
Views v2 — apps.contact admin F5 (§2.5).

Tier B: AdminContactMessageV2View — PATCH /admin/contact/messages/<id>/
         accepts {"is_read": true} (v1 had a dedicated POST /read/ action).
Tier A: AdminContactMessageReplyV2View — POST /admin/contact/messages/<id>/replies/
"""
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .views import AdminContactMessageDetailView, AdminContactMessageMarkReadView, AdminContactMessageReplyView


class AdminContactMessageV2View(APIView):
    """GET/PATCH /api/v2/admin/contact/messages/<id>/ — Tier B.

    GET  — return message detail (delegates to AdminContactMessageDetailView).
    PATCH — accepts {"is_read": true} to mark as read (v1 used POST /read/).
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, message_id):
        return AdminContactMessageDetailView().get(request, message_id=message_id)

    def patch(self, request, message_id):
        if not request.data.get('is_read'):
            return Response(
                {'detail': 'is_read requerido y debe ser true.', 'codigo_error': 'INVALID_PAYLOAD'},
                status=400,
            )
        return AdminContactMessageMarkReadView().post(request, message_id=message_id)


class AdminContactMessageReplyV2View(APIView):
    """POST /api/v2/admin/contact/messages/<id>/replies/ — Tier A."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, message_id):
        return AdminContactMessageReplyView().post(request, message_id=message_id)
