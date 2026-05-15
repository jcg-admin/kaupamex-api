"""URLs Admin — apps.orders (Sprint 19)."""
from django.urls import path
from .admin_views import (
    AdminOrderListView,
    AdminOrderDetailView,
    AdminOrderStatusUpdateView,
    AdminOrderCancelView,
    AdminDashboardView,
)

urlpatterns = [
    # UC-ORD-09 — Buscar/listar órdenes
    path('orders/',
         AdminOrderListView.as_view(), name='admin-order-list'),

    # UC-ORD-10 — Dashboard transaccional
    path('dashboard/',
         AdminDashboardView.as_view(), name='admin-dashboard'),

    # UC-ORD-07 — Detalle de orden
    path('orders/<str:order_number>/',
         AdminOrderDetailView.as_view(), name='admin-order-detail'),

    # UC-ORD-07 — Transición de estado
    path('orders/<str:order_number>/status/',
         AdminOrderStatusUpdateView.as_view(), name='admin-order-status'),

    # UC-ORD-08 — Cancelar orden
    path('orders/<str:order_number>/cancel/',
         AdminOrderCancelView.as_view(), name='admin-order-cancel'),
]
