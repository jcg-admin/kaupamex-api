"""
Views v2 — apps.contact admin F5 (§2.5).

Tier B: AdminContactMessageV2View — PATCH /admin/contact/messages/<id>/
         accepts {"is_read": true} (v1 had a dedicated POST /read/ action).
Tier A: AdminContactMessageReplyV2View — POST /admin/contact/messages/<id>/replies/
"""
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .views import AdminContactMessageMarkReadView, AdminContactMessageReplyView


class AdminContactMessageV2View(APIView):
    """PATCH /api/v2/admin/contact/messages/<id>/ — Tier B.

    v1 had a dedicated POST /messages/<id>/read/ endpoint.
    v2 accepts PATCH with {"is_read": true} on the base resource URL.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

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
