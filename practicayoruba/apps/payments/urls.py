"""URLs — apps.payments (Sprint 15)."""
from django.urls import path
from .views import (
    InitiatePaymentView, PaymentReturnView,
    InstallmentPlansView,
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
]
