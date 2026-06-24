"""
Views v2 — apps.newsletter F5 (§2.5 public + admin).

Public:
  Tier A: NewsletterSubscribeV2View
  Tier B: NewsletterUnsubscribeV2View (POST→DELETE method change)
  Tier B: NewsletterConfirmV2View (token moved from URL path to body)

Admin:
  Tier B: AdminSubscriberUnsubscribeV2View (POST→DELETE method change,
          path unsubscribe/→subscription/)
"""
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .views import (
    AdminSubscriberForceUnsubscribeView,
    NewsletterConfirmView,
    NewsletterSubscribeView,
    NewsletterUnsubscribeView,
)


class NewsletterSubscriptionsV2View(APIView):
    """POST|DELETE /api/v2/newsletter/subscriptions/.

    POST  — Tier A: delegate to NewsletterSubscribeView.
    DELETE — Tier B: delegate to NewsletterUnsubscribeView (was POST in v1).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        return NewsletterSubscribeView().post(request)

    def delete(self, request):
        return NewsletterUnsubscribeView().post(request)


class NewsletterConfirmV2View(APIView):
    """POST /api/v2/newsletter/subscriptions/confirmations/ — Tier B.

    v1 had token in URL path; v2 takes token from request body.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        token = (request.data.get('token') or '').strip()
        if not token:
            return Response(
                {'detail': 'token requerido.', 'codigo_error': 'TOKEN_REQUIRED'},
                status=400,
            )
        try:
            return NewsletterConfirmView().post(request, token=token)
        except NotFound:
            return Response(
                {'detail': 'Token inválido.', 'codigo_error': 'INVALID_TOKEN'},
                status=400,
            )


class AdminSubscriberUnsubscribeV2View(APIView):
    """DELETE /api/v2/admin/newsletter/subscribers/<id>/subscription/ — Tier B.

    v1 used POST /admin/newsletter/subscribers/<id>/unsubscribe/; v2 uses DELETE.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def delete(self, request, subscriber_id):
        return AdminSubscriberForceUnsubscribeView().post(
            request, subscriber_id=subscriber_id,
        )
