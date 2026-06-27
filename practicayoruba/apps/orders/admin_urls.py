from django.urls import path
from .admin_views import (
    AdminOrderListView,
    AdminOrderDetailView,
    AdminOrderStatusUpdateView,
    AdminOrderCancelView,
    AdminDashboardView,
)

app_name = 'admin_orders_v2'

urlpatterns = [
    path('dashboard/',
         AdminDashboardView.as_view(),              name='admin-dashboard'),
    path('orders/',
         AdminOrderListView.as_view(),              name='admin-order-list'),
    path('orders/<str:order_number>/status/',
         AdminOrderStatusUpdateView.as_view(),      name='admin-order-status'),
    path('orders/<str:order_number>/cancel/',
         AdminOrderCancelView.as_view(),            name='admin-order-cancel'),
    path('orders/<str:order_number>/',
         AdminOrderDetailView.as_view(),            name='admin-order-detail'),
]
