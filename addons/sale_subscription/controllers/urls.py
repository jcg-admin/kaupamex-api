"""URLs — addons.sale_subscription (consola L0 del operador Kaupamex)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from addons.sale_subscription.controllers.views import (
    BillingRunViewSet,
    CompanyModuleSubscriptionViewSet,
    CompanyViewSet,
    ModuleCatalogViewSet,
    ModulePriceViewSet,
    SubscriptionInvoiceViewSet,
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
router.register(
    r'billing/runs', BillingRunViewSet, basename='platform-billing-run',
)
router.register(
    r'invoices', SubscriptionInvoiceViewSet, basename='platform-invoice',
)

urlpatterns = [path('', include(router.urls))]
