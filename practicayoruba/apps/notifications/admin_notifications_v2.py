"""Admin URLs v2 — apps.notifications (F2 + F6 migrar-urls-rest-v2)."""
from django.urls import path
from .views import AdminAudienceCountView, AdminManualNotificationCreateView

app_name = 'admin_notifications_v2'

urlpatterns = [
    path('notifications/audience-count/',
         AdminAudienceCountView.as_view(), name='admin-audience-count'),
    path('notifications/',
         AdminManualNotificationCreateView.as_view(), name='admin-notifications'),
]
