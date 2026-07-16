"""
Rutas de la API v2 — apps.modules.payments
Checkout API (ADR-018) + rutas del comprador (M-10).

Registradas en config/urls.py bajo api/v2/payments/.
DEC-V2-02: los webhooks permanecen en /api/v1/payments/webhooks/* (v1 para siempre).
"""
from django.urls import path
from .views import (
    CheckoutApiPaymentView,
    MpPublicKeyView,
    MpCustomerView,
    MpCustomerCardsView,
    MpCustomerCardDetailView,
    MpCardVerifyView,
    MpPaymentMethodsView,
    ZeroDollarAuthView,
    InstallmentPlansView,
    PaymentReturnView,
    PaymentStatusView,
    PaymentHistoryView,
    RefundView,
    RetryEligibilityView,
    ReceiptPdfView,
)

app_name = 'payments_v2'

urlpatterns = [
    # Checkout API (ADR-018)
    path('initiate/',                       CheckoutApiPaymentView.as_view(),    name='checkout-api-initiate'),
    path('public-key/',                     MpPublicKeyView.as_view(),           name='mp-public-key'),
    path('customer/',                       MpCustomerView.as_view(),            name='mp-customer'),
    path('methods/',                        MpPaymentMethodsView.as_view(),      name='mp-payment-methods'),
    path('cards/',                          MpCustomerCardsView.as_view(),       name='mp-cards'),
    path('cards/validate/',                 ZeroDollarAuthView.as_view(),        name='mp-card-validate'),
    path('cards/<str:card_id>/',            MpCustomerCardDetailView.as_view(),  name='mp-card-detail'),
    path('cards/verify/<str:token>/',       MpCardVerifyView.as_view(),          name='mp-card-verify'),
    # Rutas del comprador (M-10)
    path('installments/',                                   InstallmentPlansView.as_view(),  name='installments'),
    path('<str:order_number>/return/',                      PaymentReturnView.as_view(),     name='return'),
    path('<str:order_number>/status/',                      PaymentStatusView.as_view(),     name='status'),
    path('<str:order_number>/history/',                     PaymentHistoryView.as_view(),    name='history'),
    path('<str:order_number>/refund/',                      RefundView.as_view(),            name='refund'),
    path('<str:order_number>/retry-eligibility/',           RetryEligibilityView.as_view(),  name='retry-eligibility'),
    path('<str:order_number>/receipt/',                     ReceiptPdfView.as_view(),        name='receipt'),
]
