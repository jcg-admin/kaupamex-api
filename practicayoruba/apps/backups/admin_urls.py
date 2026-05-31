"""
Admin URLs — apps.backups (UC-ADM-05).

Mounted in config/urls.py:
  path('api/v1/admin/', include('apps.backups.admin_urls', namespace='admin_backups'))
"""
from django.urls import path
from .views import AdminBackupListView, AdminBackupTriggerView

app_name = 'admin_backups'

urlpatterns = [
    path('backups/',         AdminBackupListView.as_view(),    name='backup-list'),
    path('backups/trigger/', AdminBackupTriggerView.as_view(), name='backup-trigger'),
]
