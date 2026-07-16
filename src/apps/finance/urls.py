"""
URLs — apps.finance (MOD-028).

Mounted in config/urls.py:
  path('api/v2/finance/', include(('apps.finance.urls', 'finance'), namespace='finance_v2'))

Cada UC-FIN dueña sus endpoints bajo /api/v2/finance/ (backend headless, sin
paquete ``api``). Primer slice: catalogo de conceptos (UC-FIN-06).
"""
from rest_framework.routers import DefaultRouter

from apps.finance.views import CashConceptViewSet

app_name = 'finance'

router = DefaultRouter()
router.register('concepts', CashConceptViewSet, basename='concept')

urlpatterns = router.urls
