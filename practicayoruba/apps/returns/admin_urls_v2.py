"""Admin URLs v2 — apps.returns (F3 migrar-urls-rest-v2)."""
from django.urls import path
from .views import (
    AdminReturnDetailView,
    AdminReturnListView,
    AdminReturnReceptionView,
    AdminReturnRefundView,
)
from .views_v2 import ReturnStatusV2View

app_name = 'admin_returns_v2'

urlpatterns = [
    path('', AdminReturnListView.as_view(), name='admin-list'),
    path('<int:return_id>/', AdminReturnDetailView.as_view(), name='admin-detail'),
    # Tier B: approve/reject/request-info → PATCH status
    path('<int:return_id>/status/', ReturnStatusV2View.as_view(), name='admin-status'),
    # Tier A renames
    path('<int:return_id>/receptions/', AdminReturnReceptionView.as_view(), name='admin-receptions'),
    path('<int:return_id>/refunds/', AdminReturnRefundView.as_view(), name='admin-refunds'),
]
