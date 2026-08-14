"""URLs públicas de páginas estáticas — ``website`` (UC-CFG-04).

Montado en ``config/urls.py`` bajo el mismo prefijo que la configuración::

    path('api/v2/config/', include(('addons.website.controllers.urls',
                                    'public_pages'), namespace='public_pages_v2'))
"""
from django.urls import path

from addons.website.controllers.main import PublicStaticPageView

app_name = 'public_pages'

urlpatterns = [
    path('pages/<slug:slug>/', PublicStaticPageView.as_view(), name='public-page'),
]
