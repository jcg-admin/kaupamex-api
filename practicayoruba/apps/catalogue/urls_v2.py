"""
URLs V2 — apps.catalogue

F1: /api/v2/ surface replacing fragmented /api/v1/catalogue/ endpoints.
Mounts under api/v2/ in config/urls.py.

  GET /api/v2/products/                    → ProductListV2View (list|search|autocomplete)
  GET /api/v2/products/<slug>/             → ProductDetailView
  GET /api/v2/products/<slug>/related/     → RelatedProductsView
  GET /api/v2/categories/                  → CategoryListView
  GET /api/v2/search/history/              → SearchHistoryView
  GET|DELETE /api/v2/search/history/<pk>/ → SearchHistoryDetailView
"""
from django.urls import path
from .browse_views import RelatedProductsView
from .views import CategoryListView, ProductDetailView, SearchHistoryDetailView, SearchHistoryView
from .views_v2 import ProductListV2View

app_name = 'catalogue_v2'

urlpatterns = [
    path('products/',                             ProductListV2View.as_view(),       name='product-list'),
    path('products/<slug:slug>/',                 ProductDetailView.as_view(),        name='product-detail'),
    path('products/<slug:slug>/related/',         RelatedProductsView.as_view(),      name='product-related'),
    path('categories/',                           CategoryListView.as_view(),         name='category-list'),
    path('search/history/',                       SearchHistoryView.as_view(),        name='search-history-list'),
    path('search/history/<int:pk>/',              SearchHistoryDetailView.as_view(),  name='search-history-detail'),
]
