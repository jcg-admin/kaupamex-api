"""
URLs — addons.finance (MOD-028).

Mounted in config/urls.py:
  path('api/v2/finance/', include(('addons.finance.urls', 'finance'), namespace='finance_v2'))

Cada UC-FIN dueña sus endpoints bajo /api/v2/finance/ (backend headless, sin
paquete ``api``). Primer slice: catalogo de conceptos (UC-FIN-06).
"""
from rest_framework.routers import DefaultRouter

from addons.finance.views import (
    CarrierInvoiceViewSet, CashCloseViewSet, CashConceptViewSet,
    GatewaySettlementViewSet,
)

app_name = 'finance'

router = DefaultRouter()
router.register('concepts', CashConceptViewSet, basename='concept')
router.register('reconciliations', GatewaySettlementViewSet, basename='reconciliation')
router.register('carrier-invoices', CarrierInvoiceViewSet, basename='carrier-invoice')
router.register('cash-closes', CashCloseViewSet, basename='cash-close')

urlpatterns = router.urls
