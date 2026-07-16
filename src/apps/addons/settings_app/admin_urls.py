"""Admin URLs — apps.addons.settings_app (Sprint 8, T-119, F8 consolidation)"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PaymentGatewayViewSet, ShippingMethodViewSet, ShippingZoneViewSet,
    BannerViewSet,
    StaticPageAdminListView, StaticPageAdminDetailView,
    AdminSiteSettingsView,
    StaticPagePublishView, StaticPageRestoreView,
    StaticPageStatusV2View, StaticPageRestorationV2View,
)

app_name = 'admin_settings_v2'

router = DefaultRouter()
router.register(r'gateways',         PaymentGatewayViewSet,  basename='admin-gateway')
router.register(r'shipping-methods', ShippingMethodViewSet,  basename='admin-shipping')
router.register(r'shipping-zones',   ShippingZoneViewSet,    basename='admin-shipping-zone')
router.register(r'banners',          BannerViewSet,          basename='admin-banner')

urlpatterns = [
    path('', include(router.urls)),
    path('settings/',                AdminSiteSettingsView.as_view(),     name='settings'),
    path('pages/',                   StaticPageAdminListView.as_view(),   name='page-list'),
    path('pages/<slug:slug>/',       StaticPageAdminDetailView.as_view(), name='page-detail'),
    path('pages/<slug:slug>/publish/',
         StaticPagePublishView.as_view(), name='page-publish'),
    path('pages/<slug:slug>/status/',
         StaticPageStatusV2View.as_view(), name='page-status'),
    path('pages/<slug:slug>/versions/<int:version>/restore/',
         StaticPageRestoreView.as_view(), name='page-restore-v1'),
    path('pages/<slug:slug>/restorations/',
         StaticPageRestorationV2View.as_view(), name='page-restore'),
]
