"""
Admin URLs — apps.catalogue (Sprint 6, F8 consolidation).
UC-CAT-06: CRUD de categorías para administradores.
Montado en config/urls.py como: path('api/v1/admin/', include('apps.catalogue.admin_urls'))
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .admin_views import PriceSyncsV2View, ProductDiscountStatusV2View
from .price_sync_views import PriceSyncTemplateView
from .views import (
    CategoryAdminViewSet, ProductAdminViewSet,
    ProductPriceSyncView, ProductPriceSyncConfirmView, ProductPriceSyncTemplateView,
    CatalogImportCSVView,
)
from .product_discount_views import ProductDiscountDeactivateView, ProductDiscountListCreateView

app_name = 'admin_catalogue'

router = DefaultRouter()
router.register(r'categories', CategoryAdminViewSet, basename='admin-category')
router.register(r'products',   ProductAdminViewSet,  basename='admin-product')

urlpatterns = [
    # ─── URLs específicas PRIMERO — antes del router (evita que el router capture) ───
    path('catalogue/import-csv/',
         CatalogImportCSVView.as_view(),
         name='catalogue-import-csv'),
    path('products/price-sync/',
         ProductPriceSyncView.as_view(),         name='price-sync'),
    path('products/price-sync/confirm/',
         ProductPriceSyncConfirmView.as_view(),   name='price-sync-confirm'),
    path('products/price-sync/template/',
         ProductPriceSyncTemplateView.as_view(),  name='price-sync-template'),
    # ─── Product discounts (UC-DASH-01..04) ─────────────────────────────────────────
    path('product-discounts/',
         ProductDiscountListCreateView.as_view(),
         name='product-discount-list-create'),
    path('product-discounts/<int:pk>/',
         ProductDiscountStatusV2View.as_view(),
         name='product-discount-detail'),
    path('product-discounts/<int:pk>/deactivate/',
         ProductDiscountDeactivateView.as_view(),
         name='product-discount-deactivate'),
    # ─── F8 consolidation: v2 admin paths ───────────────────────────────────────────
    path('products/imports/', CatalogImportCSVView.as_view(), name='catalogue-imports'),
    path('price-syncs/template.csv', PriceSyncTemplateView.as_view(), name='price-syncs-template'),
    path('price-syncs/', PriceSyncsV2View.as_view(), name='price-syncs'),
    # ─── Router LAST ────────────────────────────────────────────────────────────────
    path('', include(router.urls)),
]
