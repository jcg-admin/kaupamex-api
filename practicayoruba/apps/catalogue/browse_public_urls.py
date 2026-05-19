from django.urls import path

from .browse_views import CatalogueSearchView, CategoryTreeView

app_name = 'catalogue_browse_public'

urlpatterns = [
    path('categories/',        CategoryTreeView.as_view(),
         name='categories'),
    path('catalogue/search/',  CatalogueSearchView.as_view(),
         name='catalogue-search'),
]
