from django.urls import path
from .price_sync_views import PriceSyncApplyCSVView, PriceSyncApplyPercentageView, PriceSyncPreviewCSVView, PriceSyncPreviewPercentageView, PriceSyncTemplateView


app_name = 'catalogue_browse_admin'

urlpatterns = [
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
]
