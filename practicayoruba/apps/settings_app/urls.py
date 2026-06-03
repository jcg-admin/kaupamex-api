"""
URLs — apps.settings_app
Sprint 1: /api/v1/config/settings/
Sprint 8: /api/v1/admin/gateways/ y /api/v1/admin/shipping-methods/
"""
from django.urls import path
from .views import SiteSettingsView, PublicSiteSettingsView

app_name = 'settings_app'

urlpatterns = [
    path('settings/', SiteSettingsView.as_view(), name='site-settings'),
    path('public-settings/', PublicSiteSettingsView.as_view(), name='public-site-settings'),
]
