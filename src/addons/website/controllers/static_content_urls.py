"""URLs admin de contenido estático — ``website`` (UC-CFG-04).

Montado en ``config/urls.py``::

    path('api/v2/admin/',
         include(('addons.website.controllers.static_content_urls',
                  'admin_static_content'),
                 namespace='admin_static_content_v2'))

Convive con ``controllers/admin_urls.py`` (``StaticPage``): son dos modelos
distintos para el mismo UC — duplicación registrada en la iniciativa
``alinear-addon-website-referencia``, no en este pase de layout.
"""
from django.urls import path
from addons.website.controllers.static_content import StaticContentDetailView, StaticContentListView


app_name = 'admin_static_content_v2'

urlpatterns = [
    path('static-content/',          StaticContentListView.as_view(),
         name='static-content-list'),
    path('static-content/<slug:slug>/', StaticContentDetailView.as_view(),
         name='static-content-detail'),
]
