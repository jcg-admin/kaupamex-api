"""
Views v2 — apps.support.

Tier B: unifica POST close/reopen en
PATCH /api/v2/support/tickets/<id>/status/ via campo action.
"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .views import SupportTicketCloseView, SupportTicketReopenView


class SupportTicketStatusV2View(APIView):
    """PATCH /api/v2/support/tickets/<id>/status/ — Tier B."""

    permission_classes = [IsAuthenticated]

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
