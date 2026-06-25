"""
Admin URLs v2 — apps.backups F5 (§2.9).

Mounted in config/urls.py:
  path('api/v2/admin/', include('apps.backups.admin_urls_v2', namespace='admin_backups_v2'))

GET  /api/v2/admin/backups/         — list backup history
POST /api/v2/admin/backups/trigger/ — trigger on-demand backup
"""
from django.urls import path

from .views import AdminBackupListView, AdminBackupTriggerView

app_name = 'admin_backups_v2'

urlpatterns = [
    path('backups/',
         AdminBackupListView.as_view(),
         name='backup-list'),
    path('backups/trigger/',
         AdminBackupTriggerView.as_view(),
         name='backup-trigger'),
]
