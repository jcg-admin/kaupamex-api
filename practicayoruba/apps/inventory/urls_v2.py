"""Admin URLs v2 — apps.inventory (F4 migrar-urls-rest-v2)."""
from django.urls import path
from .views import (
    ProductImportReportView,
    ProductImportStatusView,
    ProductImportView,
    ZeroStockCheckView,
)
from .views_v2 import (
    StockAdjustV2View,
    StockAlertStatusV2View,
    VariantRestocksV2View,
    VariantStockV2View,
)

app_name = 'admin_inventory_v2'

urlpatterns = [
    # ── Tier A — mismo método, URL renombrada ─────────────────────────────────
    path('imports/',
         ProductImportView.as_view(),        name='imports'),
    path('imports/<str:job_id>/',
         ProductImportStatusView.as_view(),  name='import-status'),
    path('imports/<str:job_id>/report.csv',
         ProductImportReportView.as_view(),  name='import-report'),
    path('variants/<int:variant_pk>/zero-stock/',
         ZeroStockCheckView.as_view(),       name='variant-zero-stock'),

    # ── Tier B — método POST → PATCH, sufijo verbal eliminado ─────────────────
    # Específicos PRIMERO: variants/ y alerts/ antes del <product_pk> genérico.
    path('variants/<int:variant_pk>/',
         VariantStockV2View.as_view(),       name='variant-adjust'),
    path('variants/<int:variant_pk>/restocks/',
         VariantRestocksV2View.as_view(),    name='variant-restocks'),
    path('alerts/<int:pk>/',
         StockAlertStatusV2View.as_view(),   name='alert-status'),
    path('<int:product_pk>/',
         StockAdjustV2View.as_view(),        name='product-adjust'),
]
