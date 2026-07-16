"""
URLs — apps.modules.newsletter public (F8 consolidation).

Mounted in config/urls.py:
  path('api/v2/newsletter/', include(('apps.modules.newsletter.urls', 'newsletter'), namespace='newsletter_v2'))
"""
from django.urls import path
from .views import NewsletterConfirmV2View, NewsletterSubscriptionsV2View

app_name = 'newsletter'

urlpatterns = [
    path('subscriptions/', NewsletterSubscriptionsV2View.as_view(), name='subscriptions'),
    path('subscriptions/confirmations/', NewsletterConfirmV2View.as_view(), name='subscription-confirm'),
]
