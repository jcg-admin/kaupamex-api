"""URLs — addons.authz_oauth (login federado + CRUD de proveedores)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from addons.authz_oauth.views import OauthProviderViewSet, oauth_signin

app_name = 'authz_oauth'

router = DefaultRouter()
router.register(r'oauth/providers', OauthProviderViewSet,
                basename='oauth-provider')

urlpatterns = [
    path('oauth/signin/', oauth_signin, name='oauth-signin'),
    path('', include(router.urls)),
]
