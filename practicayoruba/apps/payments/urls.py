"""
URLs — apps.payments (F8 consolidation).

Mounted in config/urls.py:
  path('api/v2/payments/', include(('apps.payments.urls', 'payments'), namespace='payments_v2'))
DEC-V2-02: webhooks stay at v1 forever (external third-party URLs) — see webhook_urls.py.
"""
from django.urls import path

from .views import (
    AdminRefundView,
    InitiatePaymentView,
    InstallmentPlansView,
    PaymentHistoryView,
    PaymentReturnView,
    PaymentStatusView,
    ReceiptPdfView,
    RefundView,
    RetryEligibilityView,
)

app_name = 'payments'

urlpatterns = [
    path('initiate/', InitiatePaymentView.as_view(), name='initiate'),
    path('installments/', InstallmentPlansView.as_view(), name='installments'),
    path('<str:order_number>/return/', PaymentReturnView.as_view(), name='return'),
    path('<str:order_number>/status/', PaymentStatusView.as_view(), name='status'),
    path('<str:order_number>/history/', PaymentHistoryView.as_view(), name='history'),
    path('<str:order_number>/refund/', RefundView.as_view(), name='refund'),
    path('<str:order_number>/retry-eligibility/', RetryEligibilityView.as_view(), name='retry-eligibility'),
    path('<str:order_number>/receipt/', ReceiptPdfView.as_view(), name='receipt'),
    path('admin/<int:payment_id>/refund/', AdminRefundView.as_view(), name='admin-refund'),
]
