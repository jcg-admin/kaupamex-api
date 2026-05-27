"""Admin URLs — apps.payments (UC-PAY-11)."""
from django.urls import path
from .views import AdminPaymentListView, AdminRefundView

app_name = 'admin_payments'

urlpatterns = [
    # UC-PAY-11 — listado de transacciones para el admin
    path('payments/', AdminPaymentListView.as_view(), name='list'),
    # UC-PAY-09 — reembolso manual desde panel admin
    path('payments/<int:payment_id>/refund/',
         AdminRefundView.as_view(), name='refund'),
]
