"""URLs — apps.newsletter (public endpoints)."""
from django.urls import path
from .views import NewsletterSubscribeView, NewsletterUnsubscribeView


app_name = 'newsletter'

urlpatterns = [
    path('subscribe/',
         NewsletterSubscribeView.as_view(),
         name='subscribe'),
    path('unsubscribe/',
         NewsletterUnsubscribeView.as_view(),
         name='unsubscribe'),
]
