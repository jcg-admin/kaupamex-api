"""Platform URLs — apps.platform.company (consola L0 del operador Kaupamex)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.platform.company.views import (
    CompanyModuleSubscriptionViewSet,
    CompanyViewSet,
    ModuleCatalogViewSet,
    ModulePriceViewSet,
)

app_name = 'company'

router = DefaultRouter()
router.register(r'companies', CompanyViewSet, basename='platform-company')
router.register(r'modules', ModuleCatalogViewSet, basename='platform-module')
router.register(r'module-prices', ModulePriceViewSet, basename='platform-module-price')
router.register(
    r'module-subscriptions', CompanyModuleSubscriptionViewSet,
    basename='platform-module-subscription',
)

urlpatterns = [path('', include(router.urls))]
