from django.urls import path
from .views import (
    InventoryDashboardView,
    StockAdjustView,
    VariantStockAdjustView,
    VariantRestockView,
    VariantMovementsView,
    ZeroStockCheckView,
    StockAlertListView,
    StockAlertResolveView,
    ProductImportView,
    ProductImportStatusView,
    ProductImportReportView,
)

app_name = 'admin_inventory_v2'

urlpatterns = [
    path('inventory/',
         InventoryDashboardView.as_view(), name='dashboard'),
    path('inventory/alerts/',
         StockAlertListView.as_view(), name='alert-list'),
    path('inventory/alerts/<int:pk>/resolve/',
         StockAlertResolveView.as_view(), name='alert-resolve'),
    # Variant-specific paths BEFORE <int:product_pk> catch
    path('inventory/variants/<int:variant_pk>/zero-stock-check/',
         ZeroStockCheckView.as_view(), name='variant-zero-stock-check'),
    path('inventory/variants/<int:variant_pk>/adjust/',
         VariantStockAdjustView.as_view(), name='variant-adjust'),
    path('inventory/variants/<int:variant_pk>/restock/',
         VariantRestockView.as_view(), name='variant-restock'),
    path('inventory/variants/<int:variant_pk>/movements/',
         VariantMovementsView.as_view(), name='variant-movements'),
    path('inventory/<int:product_pk>/adjust/',
         StockAdjustView.as_view(), name='product-adjust'),
    path('inventory/import/',
         ProductImportView.as_view(), name='product-import'),
    path('inventory/import/<str:job_id>/',
         ProductImportStatusView.as_view(), name='product-import-status'),
    path('inventory/import-reports/<str:report_id>.csv',
         ProductImportReportView.as_view(), name='product-import-report'),
    # REST-style aliases matching UI expectations (no /adjust/ suffix)
    path('inventory/variants/<int:variant_pk>/',
         VariantStockAdjustView.as_view(), name='variant-adjust-alias'),
    path('inventory/imports/',
         ProductImportView.as_view(), name='product-import-plural'),
    path('inventory/<int:product_pk>/',
         StockAdjustView.as_view(), name='product-adjust-alias'),
]
