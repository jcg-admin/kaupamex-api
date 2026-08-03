"""Admin URLs — addons.mail (F8 consolidation)."""
from django.urls import path
from .main import AdminAudienceCountView, AdminManualNotificationCreateView

app_name = 'admin_notifications'

urlpatterns = [
    path('notifications/audience-count/',
         AdminAudienceCountView.as_view(), name='admin-audience-count'),
    path('notifications/',
         AdminManualNotificationCreateView.as_view(), name='admin-notifications'),
]
