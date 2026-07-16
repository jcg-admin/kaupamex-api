"""
Auth URLs v2 — apps.modules.users §2.1 F5 (F8 consolidation).

Mounted in config/urls.py:
  path('api/v2/auth/', include(('apps.modules.users.auth_urls', 'auth'), namespace='auth_v2'))

Only renames from §2.1. DEC-V2-05 sancionados (login, register, logout,
refresh, change-password) are excluded — they stay at their original path
in both v1 and v2.
"""
from django.urls import path

from .views import (
    DeactivateMeV2View,
    DeleteSessionsV2View,
    EmailVerificationV2View,
    PasswordResetConfirmV2View,
    PasswordResetV2View,
)
from .session_views import SessionListView, SessionRevokeView

app_name = 'auth'

urlpatterns = [
    path('email-verifications/',
         EmailVerificationV2View.as_view(),
         name='email-verifications'),
    path('password-resets/',
         PasswordResetV2View.as_view(),
         name='password-resets'),
    path('password-resets/confirm/',
         PasswordResetConfirmV2View.as_view(),
         name='password-resets-confirm'),
    path('me/',
         DeactivateMeV2View.as_view(),
         name='me-delete'),
    path('sessions/',
         DeleteSessionsV2View.as_view(),
         name='sessions-delete'),
    # UC-AUTH-17 (H-16): listar sesiones activas + cerrar una específica.
    path('sessions/active/',
         SessionListView.as_view(),
         name='sessions-list'),
    path('sessions/<int:pk>/revoke/',
         SessionRevokeView.as_view(),
         name='sessions-revoke'),
]
