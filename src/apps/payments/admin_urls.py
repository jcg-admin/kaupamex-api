"""Admin URLs — apps.payments (UC-PAY-11). Montado bajo /api/v2/admin/."""
from django.urls import path
from .views import (
    AdminPaymentDetailView, AdminPaymentListView,
    AdminRefundView, AdminPaymentRefundsListView,
    AdminChargebackListView, AdminChargebackDetailView,
    AdminCancelPaymentView,
)

app_name = 'admin_payments_v2'

urlpatterns = [
    # UC-PAY-11 — listado de transacciones para el admin
    path('payments/', AdminPaymentListView.as_view(), name='list'),
    # H-CICLO81-03 — detalle de un pago individual
    path('payments/<int:payment_id>/',
         AdminPaymentDetailView.as_view(), name='detail'),
    # UC-PAY-09 — reembolso manual desde panel admin
    path('payments/<int:payment_id>/refund/',
         AdminRefundView.as_view(), name='refund'),
    # T-16-D — listado de reembolsos previos de un pago
    path('payments/<int:payment_id>/refunds/',
         AdminPaymentRefundsListView.as_view(), name='refunds-list'),
    # T-CAN — cancelación proactiva de pago pendiente
    path('payments/<int:payment_id>/cancel/',
         AdminCancelPaymentView.as_view(), name='cancel'),
    # T-17-B — listado de contracargos
    path('chargebacks/',
         AdminChargebackListView.as_view(), name='chargebacks-list'),
    # T-17-C — detalle de contracargo
    path('chargebacks/<int:chargeback_id>/',
         AdminChargebackDetailView.as_view(), name='chargeback-detail'),
]
