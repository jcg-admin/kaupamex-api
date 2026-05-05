from django.urls import path
from .views import CatalogueListView, ProductDetailView, ProductSearchView

app_name = 'catalogue'

urlpatterns = [
    path('',              CatalogueListView.as_view(), name='product-list'),
    path('search/',       ProductSearchView.as_view(), name='product-search'),
    path('<slug:slug>/',  ProductDetailView.as_view(), name='product-detail'),
]
