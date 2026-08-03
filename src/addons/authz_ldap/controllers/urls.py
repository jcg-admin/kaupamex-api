"""URLs — addons.authz_ldap (CRUD de configuraciones LDAP, operador)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from addons.authz_ldap.controllers.main import CompanyLdapViewSet

app_name = 'authz_ldap'

router = DefaultRouter()
router.register(r'ldap-configs', CompanyLdapViewSet, basename='ldap-config')

urlpatterns = [
    path('', include(router.urls)),
]
