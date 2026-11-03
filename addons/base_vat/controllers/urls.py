"""URLs — ``base_vat`` (el webhook de vuelta del VIES)."""

from django.urls import path

from addons.base_vat.controllers.webhook import BaseVatWebhookController

app_name = 'base_vat'

urlpatterns = [
    path('webhook_update_vies', BaseVatWebhookController.as_view(), name='webhook_update_vies'),
]
