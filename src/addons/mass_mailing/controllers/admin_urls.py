"""Admin URLs — addons.mass_mailing (UC-NEW-03..04, backend de la newsletter).

Mounted in config/urls.py under ``api/v2/admin/`` (namespace
``admin_newsletter_v2`` conservado para no romper ``reverse()``).
"""
from django.urls import path

from addons.mass_mailing.controllers import (
    AdminCampaignCreateView,
    AdminSubscriberExportCSVView,
    AdminSubscriberForceUnsubscribeView,
    AdminSubscriberListView,
    AdminSubscriberSubscriptionDeleteView,
)

app_name = 'admin_newsletter'

urlpatterns = [
    path('newsletter/subscribers/',
         AdminSubscriberListView.as_view(),
         name='admin-subscriber-list'),
    path('newsletter/subscribers/export/',
         AdminSubscriberExportCSVView.as_view(),
         name='admin-subscriber-export'),
    path('newsletter/campaigns/',
         AdminCampaignCreateView.as_view(),
         name='admin-campaign-create'),
    path('newsletter/subscribers/<int:subscriber_id>/unsubscribe/',
         AdminSubscriberForceUnsubscribeView.as_view(),
         name='subscriber-unsubscribe'),
    path('newsletter/subscribers/<int:subscriber_id>/subscription/',
         AdminSubscriberSubscriptionDeleteView.as_view(),
         name='subscriber-subscription'),
]
