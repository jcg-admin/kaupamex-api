"""
URLs — apps.settings_app
Sprint 1: /api/v1/config/settings/
Sprint 8: /api/v1/admin/gateways/ y /api/v1/admin/shipping-methods/
"""
from django.urls import path
from .views import (
    SiteSettingsView, PublicSiteSettingsView, PublicBannerListView,
    PublicStaticPageView,
)

app_name = 'settings_app_v2'

urlpatterns = [
    path('settings/', SiteSettingsView.as_view(), name='site-settings'),
    path('public-settings/', PublicSiteSettingsView.as_view(), name='public-site-settings'),
    path('banners/', PublicBannerListView.as_view(), name='public-banners'),
    path('pages/<slug:slug>/', PublicStaticPageView.as_view(), name='public-page'),
]
