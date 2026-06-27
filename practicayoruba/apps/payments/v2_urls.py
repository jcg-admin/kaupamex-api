"""
Rutas de la API v2 — apps.payments
Checkout API (ADR-018): pago en sitio sin redirección al gateway.

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
)

app_name = 'payments_v2'

urlpatterns = [
    path('initiate/',                       CheckoutApiPaymentView.as_view(),    name='checkout-api-initiate'),
    path('public-key/',                     MpPublicKeyView.as_view(),           name='mp-public-key'),
    path('customer/',                       MpCustomerView.as_view(),            name='mp-customer'),
    path('methods/',                        MpPaymentMethodsView.as_view(),      name='mp-payment-methods'),
    path('cards/',                          MpCustomerCardsView.as_view(),       name='mp-cards'),
    path('cards/validate/',                 ZeroDollarAuthView.as_view(),        name='mp-card-validate'),
    path('cards/<str:card_id>/',            MpCustomerCardDetailView.as_view(),  name='mp-card-detail'),
    path('cards/verify/<str:token>/',       MpCardVerifyView.as_view(),          name='mp-card-verify'),
]
