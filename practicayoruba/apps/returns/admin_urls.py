"""Admin URLs — apps.returns (UC-RET-02/03/05/06, F8 consolidation)."""
from django.urls import path
from .views import (
    AdminReturnApproveView,
    AdminReturnDetailView,
    AdminReturnListView,
    AdminReturnReceptionView,
    AdminReturnRefundView,
    AdminReturnRejectView,
    AdminReturnRequestInfoView,
    ReturnStatusV2View,
)


app_name = 'admin_returns'

urlpatterns = [
    path('returns/',
         AdminReturnListView.as_view(),
         name='admin-return-list'),
    path('returns/<int:return_id>/',
         AdminReturnDetailView.as_view(),
         name='admin-return-detail'),
    path('returns/<int:return_id>/approve/',
         AdminReturnApproveView.as_view(),
         name='admin-return-approve'),
    path('returns/<int:return_id>/reject/',
         AdminReturnRejectView.as_view(),
         name='admin-return-reject'),
    path('returns/<int:return_id>/request-info/',
         AdminReturnRequestInfoView.as_view(),
         name='admin-return-request-info'),
    path('returns/<int:return_id>/reception/',
         AdminReturnReceptionView.as_view(),
         name='admin-return-reception'),
    path('returns/<int:return_id>/refund/',
         AdminReturnRefundView.as_view(),
         name='admin-return-refund'),
    path('returns/<int:return_id>/status/',
         ReturnStatusV2View.as_view(), name='admin-status'),
    path('returns/<int:return_id>/receptions/',
         AdminReturnReceptionView.as_view(), name='admin-receptions'),
    path('returns/<int:return_id>/refunds/',
         AdminReturnRefundView.as_view(), name='admin-refunds'),
]
