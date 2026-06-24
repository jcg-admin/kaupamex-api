"""
URLs v2 — apps.newsletter public F5 (§2.5).

Mounted in config/urls.py:
  path('api/v2/newsletter/', include('apps.newsletter.urls_v2', namespace='newsletter_v2'))
"""
from django.urls import path

from .views_v2 import (
    NewsletterConfirmV2View,
    NewsletterSubscriptionsV2View,
)

app_name = 'newsletter_v2'

urlpatterns = [
    path('subscriptions/',
         NewsletterSubscriptionsV2View.as_view(),
         name='subscriptions'),
    path('subscriptions/confirmations/',
         NewsletterConfirmV2View.as_view(),
         name='subscription-confirm'),
]
