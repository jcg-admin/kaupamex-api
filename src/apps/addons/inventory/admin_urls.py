"""
Admin URLs v2 — apps.addons.inventory (F8 consolidation).

Mounted in config/urls.py:
  path('api/v2/admin/inventory/', include(('apps.addons.inventory.admin_urls', 'admin_inventory_v2'), namespace='admin_inventory_v2'))
"""
from django.urls import path
from .views import (
    ProductImportReportView,
    ProductImportStatusView,
    ProductImportView,
    StockAdjustV2View,
    StockAlertStatusV2View,
    VariantRestocksV2View,
    VariantStockV2View,
    ZeroStockCheckView,
)

app_name = 'admin_inventory_v2'

urlpatterns = [
    path('imports/', ProductImportView.as_view(), name='imports'),
    path('imports/<str:job_id>/', ProductImportStatusView.as_view(), name='import-status'),
    path('imports/<str:job_id>/report.csv', ProductImportReportView.as_view(), name='import-report'),
    path('variants/<int:variant_pk>/zero-stock/', ZeroStockCheckView.as_view(), name='variant-zero-stock'),
    path('variants/<int:variant_pk>/', VariantStockV2View.as_view(), name='variant-adjust'),
    path('variants/<int:variant_pk>/restocks/', VariantRestocksV2View.as_view(), name='variant-restocks'),
    path('alerts/<int:pk>/', StockAlertStatusV2View.as_view(), name='alert-status'),
    path('<int:product_pk>/', StockAdjustV2View.as_view(), name='product-adjust'),
]
