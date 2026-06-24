"""
Auth URLs v2 — apps.users §2.1 F5.

Mounted in config/urls.py:
  path('api/v2/auth/', include('apps.users.auth_urls_v2', namespace='auth_v2'))

Only renames from §2.1. DEC-V2-05 sancionados (login, register, logout,
refresh, change-password) are excluded — they stay at their original path
in both v1 and v2.
"""
from django.urls import path

from .views_v2 import (
    DeactivateMeV2View,
    DeleteSessionsV2View,
    EmailVerificationV2View,
    PasswordResetConfirmV2View,
    PasswordResetV2View,
)

app_name = 'auth_v2'

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
]
