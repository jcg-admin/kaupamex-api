"""Webhook URLs — apps.payments.

DEC-V2-02: estos paths están registrados con MercadoPago y PayPal.
No se pueden cambiar sin coordinación con el proveedor externo.
Permanecen en /api/v1/ para siempre.
"""
from django.urls import path
from .webhooks import MercadoPagoWebhookView, PayPalWebhookView

urlpatterns = [
    path('webhooks/mercadopago/',
         MercadoPagoWebhookView.as_view(), name='webhook-mercadopago'),
    path('webhooks/paypal/',
         PayPalWebhookView.as_view(), name='webhook-paypal'),
]
