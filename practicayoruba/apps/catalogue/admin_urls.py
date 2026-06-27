from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryAdminViewSet,
    ProductAdminViewSet,
    ProductPriceSyncView,
    ProductPriceSyncConfirmView,
    ProductPriceSyncTemplateView,
    CatalogImportCSVView,
)
from .product_discount_views import (
    ProductDiscountDeactivateView,
    ProductDiscountDetailView,
    ProductDiscountListCreateView,
)
from .price_sync_views import (
    PriceSyncApplyCSVView,
    PriceSyncApplyPercentageView,
    PriceSyncPreviewCSVView,
    PriceSyncPreviewPercentageView,
    PriceSyncTemplateView,
)

app_name = 'admin_catalogue_v2'

router = DefaultRouter()
router.register(r'categories', CategoryAdminViewSet, basename='admin-category-v2')
router.register(r'products',   ProductAdminViewSet,  basename='admin-product-v2')

urlpatterns = [
    # Specific paths FIRST — before router to avoid premature capture
    path('catalogue/import-csv/',
         CatalogImportCSVView.as_view(),
         name='catalogue-import-csv'),
    path('products/price-sync/confirm/',
         ProductPriceSyncConfirmView.as_view(), name='price-sync-confirm'),
    path('products/price-sync/template/',
         ProductPriceSyncTemplateView.as_view(), name='price-sync-template'),
    path('products/price-sync/',
         ProductPriceSyncView.as_view(),         name='price-sync'),
    path('product-discounts/<int:pk>/deactivate/',
         ProductDiscountDeactivateView.as_view(),
         name='product-discount-deactivate'),
    path('product-discounts/<int:pk>/',
         ProductDiscountDetailView.as_view(),
         name='product-discount-detail'),
    path('product-discounts/',
         ProductDiscountListCreateView.as_view(),
         name='product-discount-list-create'),
    path('price-sync/preview-csv/',
         PriceSyncPreviewCSVView.as_view(),
         name='price-sync-preview-csv'),
    path('price-sync/apply-csv/',
         PriceSyncApplyCSVView.as_view(),
         name='price-sync-apply-csv'),
    path('price-sync/preview-percentage/',
         PriceSyncPreviewPercentageView.as_view(),
         name='price-sync-preview-percentage'),
    path('price-sync/apply-percentage/',
         PriceSyncApplyPercentageView.as_view(),
         name='price-sync-apply-percentage'),
    path('price-sync/template.csv',
         PriceSyncTemplateView.as_view(),
         name='price-sync-template-csv'),
    # Router LAST
    path('', include(router.urls)),
]
