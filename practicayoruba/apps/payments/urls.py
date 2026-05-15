"""URLs — apps.payments (Sprint 15)."""
from django.urls import path
from .views import (
    InitiatePaymentView, PaymentReturnView,
    InstallmentPlansView,
    PaymentStatusView, PaymentHistoryView,
    RefundView, RetryEligibilityView, AdminRefundView,
)
from .webhooks import MercadoPagoWebhookView, PayPalWebhookView

app_name = 'payments'

urlpatterns = [
    path('initiate/',
         InitiatePaymentView.as_view(), name='initiate'),
    path('installments/',
         InstallmentPlansView.as_view(), name='installments'),
    path('<str:order_number>/return/',
         PaymentReturnView.as_view(), name='return'),
    path('webhooks/mercadopago/',
         MercadoPagoWebhookView.as_view(), name='webhook-mercadopago'),
    path('webhooks/paypal/',
         PayPalWebhookView.as_view(), name='webhook-paypal'),
    # UC-PAY-05 — estado
    path('<str:order_number>/status/',
         PaymentStatusView.as_view(), name='status'),
    # UC-PAY-06 — historial
    path('<str:order_number>/history/',
         PaymentHistoryView.as_view(), name='history'),
    # UC-PAY-07 — reembolso
    path('<str:order_number>/refund/',
         RefundView.as_view(), name='refund'),
    # UC-PAY-08 — elegibilidad de reintento
    path('<str:order_number>/retry-eligibility/',
         RetryEligibilityView.as_view(), name='retry-eligibility'),
    # UC-PAY-09 — reembolso admin (nota: también en admin_urls)
    path('admin/<int:payment_id>/refund/',
         AdminRefundView.as_view(), name='admin-refund'),
]