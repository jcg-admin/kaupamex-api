"""Webhook URLs — addons.payments.

DEC-V2-02: estos paths están registrados con MercadoPago y PayPal.
No se pueden cambiar sin coordinación con el proveedor externo.
Permanecen en /api/v1/ para siempre.

InitiatePaymentView (redirect flow) also stays at v1 per M-10 design.
The v2 /payments/initiate/ serves CheckoutApiPaymentView (ADR-018 in-site).
"""
from django.urls import path
from .views import InitiatePaymentView
from .webhooks import MercadoPagoWebhookView, PayPalWebhookView

urlpatterns = [
    path('webhooks/mercadopago/',
         MercadoPagoWebhookView.as_view(), name='webhook-mercadopago'),
    path('webhooks/paypal/',
         PayPalWebhookView.as_view(), name='webhook-paypal'),
    path('initiate/', InitiatePaymentView.as_view(), name='initiate'),
]
