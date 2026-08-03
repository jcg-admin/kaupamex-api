"""``NewsletterSubscriptionsV2View`` — recurso REST subscribe/unsubscribe.

POST → alta (UC-NEW-01); DELETE → baja por token (UC-NEW-02). Delega en las
vistas de cada concern (subscribe / unsubscribe).
"""
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from .subscribe import NewsletterSubscribeView
from .unsubscribe import NewsletterUnsubscribeView


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
