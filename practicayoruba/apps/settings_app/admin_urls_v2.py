"""
Admin URLs v2 — apps.settings_app F5 (§2.9 pages).

Mounted in config/urls.py:
  path('api/v2/admin/', include('apps.settings_app.admin_urls_v2', namespace='admin_settings_v2'))
"""
from django.urls import path

from .views_v2 import StaticPageRestorationV2View, StaticPageStatusV2View

app_name = 'admin_settings_v2'

urlpatterns = [
    path('pages/<slug:slug>/status/',
         StaticPageStatusV2View.as_view(),
         name='page-status'),
    path('pages/<slug:slug>/restorations/',
         StaticPageRestorationV2View.as_view(),
         name='page-restoration'),
]
