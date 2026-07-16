"""Admin URLs — apps.modules.returns (UC-RET-02/03/05/06, F8 consolidation)."""
from django.urls import path
from .views import (
    AdminReturnDetailView,
    AdminReturnListView,
    AdminReturnReceptionView,
    AdminReturnRefundView,
    ReturnStatusV2View,
)


app_name = 'admin_returns'

urlpatterns = [
    path('',
         AdminReturnListView.as_view(),
         name='admin-return-list'),
    path('<int:return_id>/',
         AdminReturnDetailView.as_view(),
         name='admin-return-detail'),
    path('<int:return_id>/status/',
         ReturnStatusV2View.as_view(), name='admin-status'),
    path('<int:return_id>/receptions/',
         AdminReturnReceptionView.as_view(), name='admin-receptions'),
    path('<int:return_id>/refunds/',
         AdminReturnRefundView.as_view(), name='admin-refunds'),
]
