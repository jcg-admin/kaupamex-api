"""
Rutas de la API v2 — apps.returns (rutas de administración)

Registradas en config/urls.py bajo api/v2/admin/.
Mismas vistas que v1.
"""
from django.urls import path
from .views import (
    AdminReturnListView,
    AdminReturnDetailView,
    AdminReturnApproveView,
    AdminReturnRejectView,
    AdminReturnRequestInfoView,
    AdminReturnReceptionView,
    AdminReturnRefundView,
)

app_name = 'admin_returns_v2'

urlpatterns = [
    path('return-requests/',
         AdminReturnListView.as_view(),
         name='admin-return-list'),
    path('return-requests/<int:return_id>/approve/',
         AdminReturnApproveView.as_view(),
         name='admin-return-approve'),
    path('return-requests/<int:return_id>/reject/',
         AdminReturnRejectView.as_view(),
         name='admin-return-reject'),
    path('return-requests/<int:return_id>/request-info/',
         AdminReturnRequestInfoView.as_view(),
         name='admin-return-request-info'),
    path('return-requests/<int:return_id>/reception/',
         AdminReturnReceptionView.as_view(),
         name='admin-return-reception'),
    path('return-requests/<int:return_id>/refund/',
         AdminReturnRefundView.as_view(),
         name='admin-return-refund'),
    path('return-requests/<int:return_id>/',
         AdminReturnDetailView.as_view(),
         name='admin-return-detail'),
]
