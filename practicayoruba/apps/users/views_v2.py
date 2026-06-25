"""
Views v2 — apps.users auth §2.1 F5.

Tier A: PasswordResetV2View, PasswordResetConfirmV2View
Tier B: EmailVerificationV2View — merges verify + resend into one endpoint
        (dispatch by presence of 'token' key in body).
Tier B: DeactivateMeV2View — DELETE /auth/me/ (v1 used POST /me/deactivate/).
Tier B: DeleteSessionsV2View — DELETE /auth/sessions/ (v1 used POST /logout-all/).
"""
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from .views import (
    DeactivateAccountView,
    EmailVerifyView,
    LogoutAllSessionsView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ResendVerificationView,
)


class EmailVerificationV2View(APIView):
    """POST /api/v2/auth/email-verifications/ — Tier B merged endpoint.

    Merges two v1 endpoints into one:
    - Body contains 'token' key  → delegate to EmailVerifyView (verify).
    - Body contains 'email' key  → delegate to ResendVerificationView (resend).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        if 'token' in request.data:
            return EmailVerifyView().post(request)
        return ResendVerificationView().post(request)


class PasswordResetV2View(APIView):
    """POST /api/v2/auth/password-resets/ — Tier A."""
    permission_classes = [AllowAny]

    def post(self, request):
        return PasswordResetRequestView().post(request)


class PasswordResetConfirmV2View(APIView):
    """POST /api/v2/auth/password-resets/confirm/ — Tier A."""
    permission_classes = [AllowAny]

    def post(self, request):
        return PasswordResetConfirmView().post(request)


class DeactivateMeV2View(APIView):
    """DELETE /api/v2/auth/me/ — Tier B.

    v1 used POST /auth/me/deactivate/; v2 uses DELETE /auth/me/.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        return DeactivateAccountView().post(request)


class DeleteSessionsV2View(APIView):
    """DELETE /api/v2/auth/sessions/ — Tier B.

    v1 used POST /auth/logout-all/; v2 uses DELETE /auth/sessions/.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        return LogoutAllSessionsView().post(request)
