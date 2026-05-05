from django.urls import path
from .views import CatalogueListView

app_name = 'catalogue'

urlpatterns = [
    path('', CatalogueListView.as_view(), name='product-list'),
]
