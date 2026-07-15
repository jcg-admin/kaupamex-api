"""Public browse URLs — apps.catalogue (search endpoint, M-06 Fase 2)."""
from django.urls import path
from .browse_views import CatalogueSearchView

app_name = 'catalogue_browse_public'

urlpatterns = [
    path('catalogue/search/', CatalogueSearchView.as_view(), name='catalogue-search'),
]
