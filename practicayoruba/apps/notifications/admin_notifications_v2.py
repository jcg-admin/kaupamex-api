"""Admin URLs v2 — apps.notifications (F2 migrar-urls-rest-v2)."""
from django.urls import path
from .views import AdminManualNotificationCreateView

app_name = 'admin_notifications_v2'

urlpatterns = [
    path('notifications/', AdminManualNotificationCreateView.as_view(), name='admin-notifications'),
]
