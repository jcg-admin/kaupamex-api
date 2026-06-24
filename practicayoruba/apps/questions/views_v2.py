"""
Views v2 — apps.questions.

Tier B: unifica POST approve/reject en
PATCH /api/v2/admin/questions/<id>/status/ via campo action.
"""
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .views import AdminQuestionApproveView, AdminQuestionRejectView


class QuestionStatusV2View(APIView):
    """PATCH /api/v2/admin/questions/<id>/status/ — Tier B."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, question_id):
        action = (request.data.get('action') or '').strip()
        if action == 'approve':
            return AdminQuestionApproveView().post(request, question_id)
        if action == 'reject':
            return AdminQuestionRejectView().post(request, question_id)
        return Response(
            {
                'detail': "action debe ser 'approve' o 'reject'.",
                'codigo_error': 'INVALID_ACTION',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
