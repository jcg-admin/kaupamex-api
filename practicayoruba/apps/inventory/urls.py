"""Admin URLs — apps.inventory (Sprint 10)."""
from django.urls import path
from .views import (
    InventoryDashboardView, StockAdjustView,
    VariantStockAdjustView, StockAlertListView,
    ProductImportView, ProductImportStatusView,
)

app_name = 'admin_inventory'

urlpatterns = [
    path('inventory/',
         InventoryDashboardView.as_view(), name='dashboard'),
    path('inventory/alerts/',
         StockAlertListView.as_view(), name='alert-list'),
    path('inventory/<int:product_pk>/adjust/',
         StockAdjustView.as_view(), name='product-adjust'),
    path('inventory/variants/<int:variant_pk>/adjust/',
         VariantStockAdjustView.as_view(), name='variant-adjust'),
    path('inventory/import/',
         ProductImportView.as_view(), name='product-import'),
    path('inventory/import/<str:job_id>/',
         ProductImportStatusView.as_view(), name='product-import-status'),
]
