from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenBlacklistView,
)
from .views import RegisterView, ProfileView, AddressViewSet, ChangePasswordView
from .tokens import PYTokenObtainPairView

app_name = 'users'

router = DefaultRouter()
router.register(r'addresses', AddressViewSet, basename='address')

urlpatterns = [
    # Sprint 1
    path('register/',        RegisterView.as_view(),         name='register'),
    path('login/',           PYTokenObtainPairView.as_view(), name='login'),
    path('refresh/',         TokenRefreshView.as_view(),     name='token-refresh'),
    path('logout/',          TokenBlacklistView.as_view(),   name='logout'),
    # Sprint 2
    path('profile/',         ProfileView.as_view(),          name='profile'),
    path('change-password/', ChangePasswordView.as_view(),   name='change-password'),
    path('',                 include(router.urls)),
]
