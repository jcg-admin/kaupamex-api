"""
Admin URLs v2 — apps.backups F5 (§2.9).

Mounted in config/urls.py:
  path('api/v2/admin/', include('apps.backups.admin_urls_v2', namespace='admin_backups_v2'))

POST /api/v2/admin/backups/ — Tier A: same view as v1 /admin/backups/trigger/,
path shortened to resource-style.
"""
from django.urls import path

from .views import AdminBackupTriggerView

app_name = 'admin_backups_v2'

urlpatterns = [
    path('backups/',
         AdminBackupTriggerView.as_view(),
         name='backup-trigger'),
]
