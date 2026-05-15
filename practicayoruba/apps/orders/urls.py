"""URLs — apps.orders (UC-ORD-01..06)."""
from django.urls import path
from .views import (
    CheckoutView,
    OrderListView,
    OrderDetailView,
    OrderCancelView,
    OrderAddressUpdateView,
    OrderShippingUpdateView,
)

app_name = 'orders'

urlpatterns = [
    # UC-ORD-01 — Checkout
    path('checkout/',
         CheckoutView.as_view(), name='checkout'),

    # UC-ORD-03 — Listado paginado de órdenes del usuario
    path('',
         OrderListView.as_view(), name='order-list'),

    # UC-ORD-02 — Detalle de orden
    path('<str:order_number>/',
         OrderDetailView.as_view(), name='order-detail'),

    # UC-ORD-04 — Cancelar orden
    path('<str:order_number>/cancel/',
         OrderCancelView.as_view(), name='order-cancel'),

    # UC-ORD-05 — Editar dirección
    path('<str:order_number>/address/',
         OrderAddressUpdateView.as_view(), name='order-address'),

    # UC-ORD-06 — Cambiar método de envío
    path('<str:order_number>/shipping/',
         OrderShippingUpdateView.as_view(), name='order-shipping'),
]
