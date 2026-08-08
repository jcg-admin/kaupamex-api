"""URLs — addons.website_mass_mailing (superficie pública de la newsletter).

Mounted in config/urls.py:
  path('api/v2/newsletter/',
       include(('addons.website_mass_mailing.urls', 'website_mass_mailing'),
               namespace='newsletter_v2'))
"""
from django.urls import path

from . import NewsletterConfirmV2View, NewsletterSubscriptionsV2View

app_name = 'website_mass_mailing'

urlpatterns = [
    path('subscriptions/', NewsletterSubscriptionsV2View.as_view(), name='subscriptions'),
    path('subscriptions/confirmations/', NewsletterConfirmV2View.as_view(),
         name='subscription-confirm'),
]
