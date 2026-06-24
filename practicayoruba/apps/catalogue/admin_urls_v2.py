"""Admin URLs v2 — apps.catalogue (F4 migrar-urls-rest-v2)."""
from django.urls import path
from .admin_views_v2 import PriceSyncsV2View, ProductDiscountStatusV2View
from .price_sync_views import PriceSyncTemplateView
from .views import (
    CatalogImportCSVView,
    ProductPriceSyncConfirmView,
    ProductPriceSyncView,
)

app_name = 'admin_catalogue_v2'

urlpatterns = [
    # ── Tier B — catalogue/import-csv/ → products/imports/ ───────────────────
    path('products/imports/',
         CatalogImportCSVView.as_view(),        name='catalogue-imports'),

    # ── Tier B — products/price-sync/ → products/price-syncs/ ────────────────
    # Especifico template.csv ANTES de la raiz price-syncs/
    path('price-syncs/template.csv',
         PriceSyncTemplateView.as_view(),        name='price-syncs-template'),
    path('price-syncs/',
         PriceSyncsV2View.as_view(),             name='price-syncs'),

    # ── Tier B — products/price-sync/confirm/ → sub-recurso confirmations/ ───
    path('products/price-syncs/',
         ProductPriceSyncView.as_view(),         name='products-price-syncs'),
    path('products/price-syncs/confirmations/',
         ProductPriceSyncConfirmView.as_view(),  name='products-price-syncs-confirm'),

    # ── Tier B — product-discounts/<pk>/deactivate/ → PATCH <pk>/ ─────────────
    path('product-discounts/<int:pk>/',
         ProductDiscountStatusV2View.as_view(),  name='product-discount-status'),
]
