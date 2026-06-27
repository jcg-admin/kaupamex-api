"""
Rutas de la API v2 — apps.newsletter (rutas de administración)

Registradas en config/urls.py bajo api/v2/admin/.
Mismas vistas que v1.
"""
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
    # REST-style alias: DELETE /subscribers/<id>/subscription/ (F5 Tier B)
    path('newsletter/subscribers/<int:subscriber_id>/subscription/',
         AdminSubscriberSubscriptionDeleteView.as_view(),
         name='admin-subscriber-subscription-delete'),
    path('newsletter/campaigns/',
         AdminCampaignCreateView.as_view(),
         name='admin-campaign-create'),
]
