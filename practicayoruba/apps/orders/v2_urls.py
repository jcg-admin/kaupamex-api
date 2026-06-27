"""
Rutas de la API v2 — apps.orders (rutas del comprador)

Registradas en config/urls.py bajo api/v2/orders/.
Mismas vistas que v1.
"""
from django.urls import path
from .views import (
    CheckoutView,
    OrderListView,
    OrderDetailView,
    OrderCancelView,
    OrderAddressUpdateView,
    OrderShippingUpdateView,
)

app_name = 'orders_v2'

urlpatterns = [
    path('checkout/',                             CheckoutView.as_view(),             name='checkout'),
    path('',                                      OrderListView.as_view(),             name='order-list'),
    path('<str:order_number>/cancellations/',      OrderCancelView.as_view(),           name='order-cancel'),
    path('<str:order_number>/shipping-address/',   OrderAddressUpdateView.as_view(),    name='order-address'),
    path('<str:order_number>/shipping-method/',    OrderShippingUpdateView.as_view(),   name='order-shipping'),
    path('<str:order_number>/',                    OrderDetailView.as_view(),           name='order-detail'),
]
