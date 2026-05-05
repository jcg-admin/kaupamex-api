from django.urls import path
from .views import RegisterView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenBlacklistView,
)

app_name = 'users'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/',   TokenObtainPairView.as_view(),  name='login'),
    path('refresh/', TokenRefreshView.as_view(),     name='token-refresh'),
    path('logout/',  TokenBlacklistView.as_view(),   name='logout'),
]
