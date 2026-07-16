"""
URLs — apps.modules.orders (F8 consolidation).

Mounted in config/urls.py:
  path('api/v2/orders/', include(('apps.modules.orders.urls', 'orders'), namespace='orders_v2'))
"""
from django.urls import path
from .views import (
    OrderAddressUpdateView,
    OrderCancelView,
    OrderCollectionV2View,
    OrderDetailView,
    OrderShippingUpdateView,
)

app_name = 'orders'

urlpatterns = [
    path('', OrderCollectionV2View.as_view(), name='order-collection'),
    path('<str:order_number>/', OrderDetailView.as_view(), name='order-detail'),
    path('<str:order_number>/cancellations/', OrderCancelView.as_view(), name='order-cancellations'),
    path('<str:order_number>/shipping-address/', OrderAddressUpdateView.as_view(), name='order-shipping-address'),
    path('<str:order_number>/shipping-method/', OrderShippingUpdateView.as_view(), name='order-shipping-method'),
]
