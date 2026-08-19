"""URLs — addons.base_automation (webhook de reglas de automatización)."""
from django.urls import path

from addons.base_automation.controllers.main import BaseAutomationWebhookView

app_name = 'base_automation'

urlpatterns = [
    path(
        'hook/<str:rule_uuid>/', BaseAutomationWebhookView.as_view(),
        name='webhook',
    ),
]
