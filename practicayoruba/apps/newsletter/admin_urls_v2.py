"""
Admin URLs v2 — apps.newsletter F5 (§2.5).

Mounted in config/urls.py:
  path('api/v2/admin/', include('apps.newsletter.admin_urls_v2', namespace='admin_newsletter_v2'))
"""
from django.urls import path

from .views_v2 import AdminSubscriberUnsubscribeV2View

app_name = 'admin_newsletter_v2'

urlpatterns = [
    path('newsletter/subscribers/<int:subscriber_id>/subscription/',
         AdminSubscriberUnsubscribeV2View.as_view(),
         name='subscriber-subscription'),
]
