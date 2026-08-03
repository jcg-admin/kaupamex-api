"""URLs — addons.authz_passkey (passkeys WebAuthn)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from addons.authz_passkey.controllers.main import (
    PasskeyViewSet,
    auth_options,
    passkey_signin,
)

app_name = 'authz_passkey'

router = DefaultRouter()
router.register(r'passkeys', PasskeyViewSet, basename='passkey')

urlpatterns = [
    path('passkey/auth-options/', auth_options, name='auth-options'),
    path('passkey/signin/', passkey_signin, name='signin'),
    path('', include(router.urls)),
]
