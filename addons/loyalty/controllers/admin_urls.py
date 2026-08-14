"""Admin URLs — addons.loyalty (Sprint 13)."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from addons.loyalty.controllers.admin_main import VoucherViewSet

app_name = 'admin_voucher_v2'

router = DefaultRouter()
router.register(r'vouchers', VoucherViewSet, basename='admin-voucher')

urlpatterns = [path('', include(router.urls))]
