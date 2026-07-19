"""URLs — addons.notifications (user endpoints, F8 consolidation)."""
from django.urls import path
from .views import (
    NotificationListV2View,
    NotificationMarkReadV2View,
    NotificationUnreadCountView,
    NotificationPreferencesView,
)


app_name = 'notifications_v2'

urlpatterns = [
    path('',
         NotificationListV2View.as_view(),
         name='list'),
    path('unread-count/',
         NotificationUnreadCountView.as_view(),
         name='unread-count'),
    path('preferences/',
         NotificationPreferencesView.as_view(),
         name='preferences'),
    path('<int:pk>/',
         NotificationMarkReadV2View.as_view(),
         name='notification-detail'),
]
