"""
Admin URLs — addons.website (UC-CFG-04).

Mounted in config/urls.py as:
  path('api/v1/admin/', include('addons.website.admin_urls',
       namespace='admin_static_content'))
"""
from django.urls import path
from .views import StaticContentDetailView, StaticContentListView


app_name = 'admin_static_content_v2'

urlpatterns = [
    path('static-content/',          StaticContentListView.as_view(),
         name='static-content-list'),
    path('static-content/<slug:slug>/', StaticContentDetailView.as_view(),
         name='static-content-detail'),
]
