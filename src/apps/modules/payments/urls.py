"""
URLs — apps.modules.payments (F8 consolidation, M-10 Fase 2).

Mounted in config/urls.py:
  path('api/v2/payments/', include(('apps.modules.payments.urls', 'payments'), namespace='payments_v2'))
DEC-V2-02: webhooks stay at v1 forever (external third-party URLs) — see webhook_urls.py.
M-10: InitiatePaymentView (redirect flow) stays at /api/v1/payments/initiate/ via
webhook_urls.py; CheckoutApiPaymentView (ADR-018 in-site) lives here at /initiate/.

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
    CheckoutApiPaymentView,
    MercadoPagoInitiateView,
    MpPublicKeyView,
    MpCustomerView,
    MpCustomerCardsView,
    MpCustomerCardDetailView,
    MpCardVerifyView,
    MpPaymentMethodsView,
    ZeroDollarAuthView,
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
    # Redirect-flow gateway endpoint (URL-implicit gateway, no `gateway` in body)
    path('mercadopago/',                 MercadoPagoInitiateView.as_view(),  name='mercadopago-initiate'),
    # Checkout API (ADR-018) — in-site CardForm flow
    path('initiate/',                    CheckoutApiPaymentView.as_view(),   name='initiate'),
    path('public-key/',                  MpPublicKeyView.as_view(),          name='mp-public-key'),
    path('customer/',                    MpCustomerView.as_view(),           name='mp-customer'),
    path('methods/',                     MpPaymentMethodsView.as_view(),     name='mp-payment-methods'),
    path('cards/',                       MpCustomerCardsView.as_view(),      name='mp-cards'),
    path('cards/validate/',              ZeroDollarAuthView.as_view(),       name='mp-card-validate'),
    path('cards/<str:card_id>/',         MpCustomerCardDetailView.as_view(), name='mp-card-detail'),
    path('cards/verify/<str:token>/',    MpCardVerifyView.as_view(),         name='mp-card-verify'),
    # Buyer routes (M-10)
    path('installments/',                             InstallmentPlansView.as_view(),  name='installments'),
    path('<str:order_number>/return/',                PaymentReturnView.as_view(),     name='return'),
    path('<str:order_number>/status/',                PaymentStatusView.as_view(),     name='status'),
    path('<str:order_number>/history/',               PaymentHistoryView.as_view(),    name='history'),
    path('<str:order_number>/refund/',                RefundView.as_view(),            name='refund'),
    path('<str:order_number>/retry-eligibility/',     RetryEligibilityView.as_view(),  name='retry-eligibility'),
    path('<str:order_number>/receipt/',               ReceiptPdfView.as_view(),        name='receipt'),
    # Admin (moved from webhook_urls v1 — admin refunds are a v2 concern)
    path('admin/<int:payment_id>/refund/',            AdminRefundView.as_view(),       name='admin-refund'),
]
