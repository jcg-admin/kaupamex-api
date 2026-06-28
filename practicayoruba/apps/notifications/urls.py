"""URLs — apps.notifications (user endpoints)."""
from django.urls import path
from .views import NotificationListView, NotificationMarkAllReadView, NotificationMarkReadView, NotificationPreferencesView, NotificationUnreadCountView


app_name = 'notifications_v2'

urlpatterns = [
    path('',
         NotificationListView.as_view(),
         name='list'),
    path('unread-count/',
         NotificationUnreadCountView.as_view(),
         name='unread-count'),
    path('read-all/',
         NotificationMarkAllReadView.as_view(),
         name='read-all'),
    path('preferences/',
         NotificationPreferencesView.as_view(),
         name='preferences'),
    path('<int:notification_id>/read/',
         NotificationMarkReadView.as_view(),
         name='mark-read'),
]
