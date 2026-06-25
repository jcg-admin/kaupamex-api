"""
URLs — apps.catalogue (F8 consolidation).

Mounted in config/urls.py:
  path('api/v2/', include(('apps.catalogue.urls', 'catalogue'), namespace='catalogue_v2'))
"""
from django.urls import path
from .browse_views import RelatedProductsView
from .views import CategoryListView, ProductDetailView, ProductListV2View

app_name = 'catalogue'

urlpatterns = [
    path('products/', ProductListV2View.as_view(), name='product-list'),
    path('products/<slug:slug>/', ProductDetailView.as_view(), name='product-detail'),
    path('products/<slug:slug>/related/', RelatedProductsView.as_view(), name='product-related'),
    path('categories/', CategoryListView.as_view(), name='category-list'),
]
