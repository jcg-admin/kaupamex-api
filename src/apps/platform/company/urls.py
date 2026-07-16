"""Platform URLs — apps.platform.company (consola L0 del operador Kaupamex)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.platform.company.views import CompanyModuleSubscriptionViewSet, CompanyViewSet

app_name = 'company'

router = DefaultRouter()
router.register(r'companies', CompanyViewSet, basename='platform-company')
router.register(
    r'module-subscriptions', CompanyModuleSubscriptionViewSet,
    basename='platform-module-subscription',
)

urlpatterns = [path('', include(router.urls))]
