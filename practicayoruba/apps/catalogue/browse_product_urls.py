from django.urls import path
from .browse_views import RelatedProductsView


app_name = 'catalogue_browse_product'

urlpatterns = [
    path('<slug:slug>/related/', RelatedProductsView.as_view(),
         name='product-related'),
]
