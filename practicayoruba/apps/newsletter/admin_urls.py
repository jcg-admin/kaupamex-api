"""Admin URLs — apps.newsletter (UC-NEW-03..04, F8 consolidation)."""
from django.urls import path
from .views import (
    AdminCampaignCreateView,
    AdminSubscriberForceUnsubscribeView,
    AdminSubscriberListView,
    AdminSubscriberUnsubscribeV2View,
)


app_name = 'admin_newsletter'

urlpatterns = [
    path('newsletter/subscribers/',
         AdminSubscriberListView.as_view(),
         name='admin-subscriber-list'),
    path('newsletter/subscribers/<int:subscriber_id>/unsubscribe/',
         AdminSubscriberForceUnsubscribeView.as_view(),
         name='admin-subscriber-force-unsub'),
    path('newsletter/campaigns/',
         AdminCampaignCreateView.as_view(),
         name='admin-campaign-create'),
    path('newsletter/subscribers/<int:subscriber_id>/subscription/',
         AdminSubscriberUnsubscribeV2View.as_view(),
         name='subscriber-subscription'),
]
