"""
Rutas de la API v2 — apps.newsletter (rutas públicas)

Registradas en config/urls.py bajo api/v2/newsletter/.
Mismas vistas que v1.
"""
from django.urls import path
from .views import (
    NewsletterSubscribeView,
    NewsletterConfirmView,
    NewsletterUnsubscribeView,
    NewsletterSubscriptionView,
)

app_name = 'newsletter_v2'

urlpatterns = [
    # REST-style alias: POST (subscribe) + DELETE (unsubscribe) at /subscriptions/
    path('subscriptions/',
         NewsletterSubscriptionView.as_view(),
         name='subscriptions'),
    # Legacy-style paths (same views, preserved for backwards compat)
    path('subscribe/',
         NewsletterSubscribeView.as_view(),
         name='subscribe'),
    path('confirm/<str:token>/',
         NewsletterConfirmView.as_view(),
         name='confirm'),
    path('unsubscribe/',
         NewsletterUnsubscribeView.as_view(),
         name='unsubscribe'),
]
