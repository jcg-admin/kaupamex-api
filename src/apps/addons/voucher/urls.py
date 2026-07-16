"""Admin URLs — apps.addons.voucher (Sprint 13)."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import VoucherViewSet

app_name = 'admin_voucher_v2'

router = DefaultRouter()
router.register(r'vouchers', VoucherViewSet, basename='admin-voucher')

urlpatterns = [path('', include(router.urls))]
