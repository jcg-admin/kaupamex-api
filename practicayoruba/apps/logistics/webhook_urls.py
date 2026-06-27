from django.urls import path
from .webhooks import CourierWebhookView

# DEC-V2-02: logistics webhook stays on /api/v1/logistics/ FOREVER
urlpatterns = [
    path('webhook/courier/', CourierWebhookView.as_view(), name='courier-webhook'),
]
