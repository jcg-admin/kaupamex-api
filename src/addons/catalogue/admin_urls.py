"""
Admin URLs — addons.catalogue (Sprint 6, F8 consolidation).
UC-CAT-06: CRUD de categorías para administradores.
Montado en config/urls.py como: path('api/v2/admin/', include('addons.catalogue.admin_urls'))
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .admin_views import PriceSyncsV2View, ProductDiscountStatusV2View
from .price_sync_views import PriceSyncTemplateView
from .views import (
    CategoryAdminViewSet, ProductAdminViewSet,
    CatalogImportCSVView,
)
from .product_discount_views import ProductDiscountListCreateView

app_name = 'admin_catalogue'

router = DefaultRouter()
router.register(r'categories', CategoryAdminViewSet, basename='admin-category')
router.register(r'products',   ProductAdminViewSet,  basename='admin-product')

urlpatterns = [
    # ─── Product discounts (UC-DASH-01..04) ─────────────────────────────────────────
    path('product-discounts/',
         ProductDiscountListCreateView.as_view(),
         name='product-discount-list-create'),
    path('product-discounts/<int:pk>/',
         ProductDiscountStatusV2View.as_view(),
         name='product-discount-detail'),
    # ─── v2 canonical admin paths ────────────────────────────────────────────────────
    path('products/imports/', CatalogImportCSVView.as_view(), name='catalogue-imports'),
    path('price-syncs/template.csv', PriceSyncTemplateView.as_view(), name='price-syncs-template'),
    path('price-syncs/', PriceSyncsV2View.as_view(), name='price-syncs'),
    # ─── Router LAST ────────────────────────────────────────────────────────────────
    path('', include(router.urls)),
]
