"""URLs del backoffice de ventas.

Montado en ``config/urls.py`` bajo ``api/v2/admin/``, junto al resto de las
superficies admin.
"""
from django.urls import path

from .admin_views import AdminOrderDetailView, AdminOrderListView

urlpatterns = [
    path('orders/', AdminOrderListView.as_view(), name='admin-order-list'),
    path('orders/<str:order_number>/', AdminOrderDetailView.as_view(),
         name='admin-order-detail'),
]
