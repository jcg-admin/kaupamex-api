from django.urls import path
from .views import (
    CatalogueListView,
    ProductDetailView,
    AutocompleteView,
    SearchHistoryView,
    SearchHistoryDetailView,
    CategoryListView,
)
from .browse_views import CatalogueSearchView, CategoryTreeView, RelatedProductsView
from apps.chartsize.views import VariantSingleView

app_name = 'catalogue_v2'

urlpatterns = [
    path('',                         CatalogueListView.as_view(),       name='product-list'),
    path('autocomplete/',            AutocompleteView.as_view(),         name='autocomplete'),
    path('search/',                  CatalogueSearchView.as_view(),      name='product-search'),
    path('search/history/',          SearchHistoryView.as_view(),        name='search-history-list'),
    path('search/history/<int:pk>/', SearchHistoryDetailView.as_view(),  name='search-history-detail'),
    path('categories/',              CategoryListView.as_view(),         name='category-list'),
    path('categories/tree/',         CategoryTreeView.as_view(),         name='category-tree'),
    # slug catch-alls LAST — specific prefixes must precede these
    path('<slug:slug>/variants/<int:pk>/', VariantSingleView.as_view(), name='variant-single'),
    path('<slug:slug>/related/',     RelatedProductsView.as_view(),      name='product-related'),
    path('<slug:slug>/',             ProductDetailView.as_view(),        name='product-detail'),
]
