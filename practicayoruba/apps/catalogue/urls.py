"""
URLs — apps.catalogue

Sprint 4: GET /api/v1/catalogue/
Sprint 5: GET /api/v1/catalogue/<slug>/, GET /api/v1/catalogue/search/
Sprint 6: GET /api/v1/catalogue/autocomplete/
          GET|DELETE /api/v1/catalogue/search/history/
          GET|DELETE /api/v1/catalogue/search/history/<pk>/
          GET|POST|PATCH|DELETE /api/v1/admin/categories/  (admin_urls)
"""
from django.urls import path
from .views import (
    CatalogueListView,
    ProductDetailView,
    ProductSearchView,
    AutocompleteView,
    SearchHistoryView,
    SearchHistoryDetailView,
    CategoryListView,
)

app_name = 'catalogue'

urlpatterns = [
    path('',              CatalogueListView.as_view(),    name='product-list'),
    path('autocomplete/', AutocompleteView.as_view(),      name='autocomplete'),
    path('search/',       ProductSearchView.as_view(),     name='product-search'),
    path('search/history/',
         SearchHistoryView.as_view(),      name='search-history-list'),
    path('search/history/<int:pk>/',
         SearchHistoryDetailView.as_view(), name='search-history-detail'),
    path('categories/',   CategoryListView.as_view(),    name='category-list'),
    path('<slug:slug>/',  ProductDetailView.as_view(),    name='product-detail'),
]
