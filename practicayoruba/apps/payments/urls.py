"""
URLs — apps.payments (F8 consolidation).

Mounted in config/urls.py:
  path('api/v2/payments/', include(('apps.payments.urls', 'payments'), namespace='payments_v2'))
DEC-V2-02: webhooks stay at v1 forever (external third-party URLs) — see webhook_urls.py.

DEC-PAY-01 (2026-06-26): PayPal gateway infrastructure (PayPalGateway, services,
models) is fully implemented but the /paypal/ endpoint is NOT exposed.
Enabling PayPal as an accepted payment method is a business decision pending
evaluation by the e-commerce team (operational cost, tax reporting, Mexico
market penetration vs MercadoPago). When the team decides to enable PayPal,
add: path('paypal/', PayPalInitiateView.as_view(), name='paypal-initiate')
and implement PayPalInitiateView mirroring MercadoPagoInitiateView with
gateway_type='PAYPAL'. No code changes are needed in gateways/ or services.py.
"""
from django.urls import path

from .views import (
    AdminRefundView,
    InitiatePaymentView,
    MercadoPagoInitiateView,
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
    # Gateway-specific initiation endpoints (F6 Tier B, GAP-I1).
    # /mercadopago/ is the canonical v2 endpoint; gateway is implied by URL.
    # /initiate/ is kept as a deprecated alias for UI backwards-compat (OBS-U1).
    path('mercadopago/', MercadoPagoInitiateView.as_view(), name='mercadopago-initiate'),
    path('initiate/', InitiatePaymentView.as_view(), name='initiate'),  # deprecated → OBS-U1
    path('installments/', InstallmentPlansView.as_view(), name='installments'),
    path('<str:order_number>/return/', PaymentReturnView.as_view(), name='return'),
    path('<str:order_number>/status/', PaymentStatusView.as_view(), name='status'),
    path('<str:order_number>/history/', PaymentHistoryView.as_view(), name='history'),
    path('<str:order_number>/refund/', RefundView.as_view(), name='refund'),
    path('<str:order_number>/retry-eligibility/', RetryEligibilityView.as_view(), name='retry-eligibility'),
    path('<str:order_number>/receipt/', ReceiptPdfView.as_view(), name='receipt'),
    path('admin/<int:payment_id>/refund/', AdminRefundView.as_view(), name='admin-refund'),
]
