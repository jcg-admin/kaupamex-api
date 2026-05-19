"""Admin URLs — apps.inventory (Sprint 10 + UI contract 2026-05)."""
from django.urls import path
from .views import (
    InventoryDashboardView, StockAdjustView,
    VariantStockAdjustView, VariantMovementsView, StockAlertListView,
    ProductImportView, ProductImportStatusView,
)

app_name = 'admin_inventory'

urlpatterns = [
    path('inventory/',
         InventoryDashboardView.as_view(), name='dashboard'),
    path('inventory/alerts/',
         StockAlertListView.as_view(), name='alert-list'),

    # URLs específicas de variante (UI contract UC-INV-02..04)
    # — DEBEN ir antes del <int:product_pk> catch para no chocar.
    path('inventory/variants/<int:variant_pk>/adjust/',
         VariantStockAdjustView.as_view(), name='variant-adjust'),
    path('inventory/variants/<int:variant_pk>/movements/',
         VariantMovementsView.as_view(), name='variant-movements'),

    path('inventory/<int:product_pk>/adjust/',
         StockAdjustView.as_view(), name='product-adjust'),
    path('inventory/import/',
         ProductImportView.as_view(), name='product-import'),
    path('inventory/import/<str:job_id>/',
         ProductImportStatusView.as_view(), name='product-import-status'),
]
