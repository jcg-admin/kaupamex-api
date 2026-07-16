"""Webhook URLs — apps.modules.logistics.

DEC-V2-02: el webhook del courier está registrado con el proveedor
externo y no se puede cambiar sin coordinación. Permanece en /api/v1/.
"""
from django.urls import path
from .webhooks import CourierWebhookView

urlpatterns = [
    path('webhook/courier/',
         CourierWebhookView.as_view(), name='courier-webhook'),
]
