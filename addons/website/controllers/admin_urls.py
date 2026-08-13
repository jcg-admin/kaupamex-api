"""URLs admin de páginas estáticas — ``website`` (UC-CFG-04).

Montado en ``config/urls.py``::

    path('api/v2/admin/', include(('addons.website.controllers.admin_urls',
                                   'admin_pages'), namespace='admin_pages_v2'))
"""
from django.urls import path

from addons.website.controllers.main import (
    StaticPageAdminDetailView,
    StaticPageAdminListView,
    StaticPageRestorationV2View,
    StaticPageStatusV2View,
)

app_name = 'admin_pages'

urlpatterns = [
    path('pages/', StaticPageAdminListView.as_view(), name='page-list'),
    # Las rutas específicas van antes del detalle por slug.
    path('pages/<slug:slug>/status/', StaticPageStatusV2View.as_view(),
         name='page-status'),
    path('pages/<slug:slug>/restorations/', StaticPageRestorationV2View.as_view(),
         name='page-restorations'),
    path('pages/<slug:slug>/', StaticPageAdminDetailView.as_view(),
         name='page-detail'),
]
