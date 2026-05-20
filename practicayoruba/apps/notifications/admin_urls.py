"""Admin URLs — apps.notifications (UC-NOT-07)."""
from django.urls import path
from .views import AdminAudienceCountView, AdminManualNotificationCreateView


app_name = 'admin_notifications'

urlpatterns = [
    path('notifications/audience-count/',
         AdminAudienceCountView.as_view(),
         name='admin-audience-count'),
    path('notifications/manual/',
         AdminManualNotificationCreateView.as_view(),
         name='admin-manual-create'),
]
