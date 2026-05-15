"""Admin URLs — apps.settings_app (Sprint 8)"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (PaymentGatewayViewSet, ShippingMethodViewSet,
                    StaticPageAdminView, StaticPagePublishView,
                    StaticPageRestoreView)

app_name = 'admin_settings'

router = DefaultRouter()
router.register(r'gateways',         PaymentGatewayViewSet,  basename='admin-gateway')
router.register(r'shipping-methods', ShippingMethodViewSet,  basename='admin-shipping')

urlpatterns = [
    path('', include(router.urls)),
    path('pages/',                              StaticPageAdminView.as_view(),   name='page-list'),
    path('pages/<slug:slug>/',                  StaticPageAdminView.as_view(),   name='page-detail'),
    path('pages/<slug:slug>/publish/',          StaticPagePublishView.as_view(),  name='page-publish'),
    path('pages/<slug:slug>/versions/<int:version>/restore/',
         StaticPageRestoreView.as_view(), name='page-restore'),
]
