"""Admin URLs — apps.modules.newsletter (UC-NEW-03..04, F8 consolidation)."""
from django.urls import path
from .views import (
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
