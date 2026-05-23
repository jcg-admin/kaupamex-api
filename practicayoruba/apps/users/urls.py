from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RegisterView, ProfileView, AddressViewSet, ChangePasswordView, PasswordResetRequestView, PasswordResetConfirmView, EmailVerifyView, ResendVerificationView, DeactivateAccountView, LogoutAllSessionsView
from .tokens import PYTokenObtainPairView, PYTokenRefreshView, PYTokenBlacklistView

app_name = 'users'

router = DefaultRouter()
router.register(r'addresses', AddressViewSet, basename='address')

urlpatterns = [
    # Sprint 1
    path('register/',        RegisterView.as_view(),         name='register'),
    path('login/',           PYTokenObtainPairView.as_view(), name='login'),
    path('refresh/',         PYTokenRefreshView.as_view(),   name='token-refresh'),
    path('logout/',          PYTokenBlacklistView.as_view(), name='logout'),
    # Sprint 2
    path('profile/',         ProfileView.as_view(),          name='profile'),
    path('change-password/', ChangePasswordView.as_view(),   name='change-password'),
    path('',                 include(router.urls)),
    # Sprint 3
    path('password-reset/',          PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset/confirm/',  PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('verify-email/',            EmailVerifyView.as_view(),           name='verify-email'),
    path('resend-verification/',     ResendVerificationView.as_view(),    name='resend-verification'),
    # UC-AUTH-16: auto soft-delete por el usuario autenticado.
    path('me/deactivate/',           DeactivateAccountView.as_view(),     name='me-deactivate'),
    # UC-AUTH: cerrar todas las sesiones activas (logout all devices).
    path('logout-all/',              LogoutAllSessionsView.as_view(),     name='logout-all'),
]
