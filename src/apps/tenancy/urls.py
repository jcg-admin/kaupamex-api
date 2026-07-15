"""Platform URLs — apps.tenancy (consola L0 del operador Kaupamex)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.tenancy.views import TenantViewSet

app_name = 'tenancy_v2'

router = DefaultRouter()
router.register(r'tenants', TenantViewSet, basename='platform-tenant')

urlpatterns = [path('', include(router.urls))]
