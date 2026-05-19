"""
Admin URLs — apps.static_content (UC-CFG-04).

Mounted in config/urls.py as:
  path('api/v1/admin/', include('apps.static_content.admin_urls',
       namespace='admin_static_content'))
"""
from django.urls import path

from .views import StaticContentDetailView, StaticContentListView

app_name = 'admin_static_content'

urlpatterns = [
    path('static-content/',          StaticContentListView.as_view(),
         name='static-content-list'),
    path('static-content/<slug:slug>/', StaticContentDetailView.as_view(),
         name='static-content-detail'),
]
