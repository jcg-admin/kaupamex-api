"""URLs v2 — apps.orders (F3 migrar-urls-rest-v2)."""
from django.urls import path
from .views import (
    OrderAddressUpdateView,
    OrderCancelView,
    OrderDetailView,
    OrderListView,
    OrderShippingUpdateView,
)

app_name = 'orders_v2'

urlpatterns = [
    path('', OrderListView.as_view(), name='order-list'),
    path('<str:order_number>/', OrderDetailView.as_view(), name='order-detail'),
    # Tier A renames
    path('<str:order_number>/cancellations/', OrderCancelView.as_view(), name='order-cancellations'),
    path('<str:order_number>/shipping-address/', OrderAddressUpdateView.as_view(), name='order-shipping-address'),
    path('<str:order_number>/shipping-method/', OrderShippingUpdateView.as_view(), name='order-shipping-method'),
]
