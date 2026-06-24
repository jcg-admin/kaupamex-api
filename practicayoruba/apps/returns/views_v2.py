"""
Views v2 — apps.returns.

Tier B: unifica POST approve/reject/request-info en
PATCH /api/v2/admin/return-requests/<id>/status/ via campo action.
"""
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .views import (
    AdminReturnApproveView,
    AdminReturnRejectView,
    AdminReturnRequestInfoView,
)


class ReturnStatusV2View(APIView):
    """PATCH /api/v2/admin/return-requests/<id>/status/ — Tier B."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, return_id):
        action = (request.data.get('action') or '').strip()
        if action == 'approve':
            return AdminReturnApproveView().post(request, return_id)
        if action == 'reject':
            return AdminReturnRejectView().post(request, return_id)
        if action == 'request_info':
            return AdminReturnRequestInfoView().post(request, return_id)
        return Response(
            {
                'detail': "action debe ser 'approve', 'reject' o 'request_info'.",
                'codigo_error': 'INVALID_ACTION',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
