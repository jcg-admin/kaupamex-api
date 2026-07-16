"""Auth URLs v2 — apps.modules.users (M-20). Montado bajo /api/v2/auth/.

DEC-V2-05: v1 (/api/v1/auth/) permanece activo PARA SIEMPRE.
Este archivo sólo agrega v2 — no reemplaza v1.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView, ProfileView, AddressViewSet, ChangePasswordView,
    PasswordResetRequestView, PasswordResetConfirmView, EmailVerifyView,
    ResendVerificationView, DeactivateAccountView, LogoutAllSessionsView,
)
from .tokens import PYTokenObtainPairView, PYTokenRefreshView, PYTokenBlacklistView

app_name = 'users_v2'

router = DefaultRouter()
router.register(r'addresses', AddressViewSet, basename='address')

urlpatterns = [
    path('register/',             RegisterView.as_view(),              name='register'),
    path('login/',                PYTokenObtainPairView.as_view(),     name='login'),
    path('refresh/',              PYTokenRefreshView.as_view(),        name='token-refresh'),
    path('logout/',               PYTokenBlacklistView.as_view(),      name='logout'),
    path('profile/',              ProfileView.as_view(),               name='profile'),
    path('change-password/',      ChangePasswordView.as_view(),        name='change-password'),
    path('',                      include(router.urls)),
    path('password-reset/',         PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('verify-email/',           EmailVerifyView.as_view(),          name='verify-email'),
    path('resend-verification/',    ResendVerificationView.as_view(),   name='resend-verification'),
    path('me/deactivate/',          DeactivateAccountView.as_view(),    name='me-deactivate'),
    path('logout-all/',             LogoutAllSessionsView.as_view(),    name='logout-all'),
]
