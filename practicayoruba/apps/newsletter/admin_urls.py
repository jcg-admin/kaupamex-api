from django.urls import path
from .views import (
    AdminSubscriberListView,
    AdminSubscriberForceUnsubscribeView,
    AdminSubscriberSubscriptionDeleteView,
    AdminCampaignCreateView,
)

app_name = 'admin_newsletter_v2'

urlpatterns = [
    path('newsletter/subscribers/',
         AdminSubscriberListView.as_view(),
         name='admin-subscriber-list'),
    path('newsletter/subscribers/<int:subscriber_id>/unsubscribe/',
         AdminSubscriberForceUnsubscribeView.as_view(),
         name='admin-subscriber-force-unsub'),
    # REST-style: DELETE /subscribers/<id>/subscription/ (F5 Tier B)
    path('newsletter/subscribers/<int:subscriber_id>/subscription/',
         AdminSubscriberSubscriptionDeleteView.as_view(),
         name='admin-subscriber-subscription-delete'),
    path('newsletter/campaigns/',
         AdminCampaignCreateView.as_view(),
         name='admin-campaign-create'),
]
