"""URLs — apps.newsletter (public endpoints)."""
from django.urls import path
from .views import NewsletterConfirmView, NewsletterSubscribeView, NewsletterUnsubscribeView


app_name = 'newsletter'

urlpatterns = [
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
