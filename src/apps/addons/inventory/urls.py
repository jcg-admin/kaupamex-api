"""Admin URLs — apps.addons.inventory (Sprint 10 + UI contract 2026-05)."""
from django.urls import path
from .views import (
    InventoryDashboardView,
    VariantMovementsView,
    StockAlertListView,
    StockAdjustV2View,
    VariantStockV2View,
    VariantRestocksV2View,
    StockAlertStatusV2View,
    ZeroStockCheckView,
    ProductImportView,
    ProductImportStatusView,
    ProductImportReportView,
)

app_name = 'admin_inventory'

urlpatterns = [
    # ─── Read-only / dashboard ───────────────────────────────────────────────
    path('inventory/',
         InventoryDashboardView.as_view(), name='dashboard'),
    path('inventory/alerts/',
         StockAlertListView.as_view(), name='alert-list'),
    path('inventory/variants/<int:variant_pk>/movements/',
         VariantMovementsView.as_view(), name='variant-movements'),

    # ─── v2 canonical: imports ───────────────────────────────────────────────
    path('inventory/imports/',
         ProductImportView.as_view(), name='inventory-imports'),
    path('inventory/imports/<str:job_id>/',
         ProductImportStatusView.as_view(), name='inventory-import-status'),
    path('inventory/import-reports/<str:report_id>.csv',
         ProductImportReportView.as_view(), name='inventory-import-report'),

    # ─── v2 canonical: alert status ──────────────────────────────────────────
    path('inventory/alerts/<int:pk>/',
         StockAlertStatusV2View.as_view(), name='alert-status'),

    # ─── v2 canonical: variant-specific (more specific before generic) ───────
    path('inventory/variants/<int:variant_pk>/zero-stock/',
         ZeroStockCheckView.as_view(), name='variant-zero-stock'),
    path('inventory/variants/<int:variant_pk>/restocks/',
         VariantRestocksV2View.as_view(), name='variant-restocks'),
    path('inventory/variants/<int:variant_pk>/',
         VariantStockV2View.as_view(), name='variant-adjust'),

    # ─── v2 canonical: product adjust ────────────────────────────────────────
    path('inventory/<int:product_pk>/',
         StockAdjustV2View.as_view(), name='product-adjust'),
]
