"""
Views v2 — apps.reviews.

Tier B: unifica POST approve/reject en
PATCH /api/v2/admin/reviews/<pk>/status/ via campo action.
"""
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .views import ReviewApproveView, ReviewRejectView


class ReviewStatusV2View(APIView):
    """PATCH /api/v2/admin/reviews/<pk>/status/ — Tier B."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, pk):
        action = (request.data.get('action') or '').strip()
        if action == 'approve':
            return ReviewApproveView().post(request, pk)
        if action == 'reject':
            return ReviewRejectView().post(request, pk)
        return Response(
            {
                'detail': "action debe ser 'approve' o 'reject'.",
                'codigo_error': 'INVALID_ACTION',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
