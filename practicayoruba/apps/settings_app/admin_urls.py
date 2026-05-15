"""Admin URLs — apps.settings_app (Sprint 8)"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaymentGatewayViewSet, ShippingMethodViewSet

app_name = 'admin_settings'

router = DefaultRouter()
router.register(r'gateways',         PaymentGatewayViewSet,  basename='admin-gateway')
router.register(r'shipping-methods', ShippingMethodViewSet,  basename='admin-shipping')

urlpatterns = [
    path('', include(router.urls)),
]
