"""
Admin URLs — apps.modules.backups (UC-ADM-05).

Mounted in config/urls.py under api/v2/admin/:

  GET  /api/v2/admin/backups/  — historial paginado
  POST /api/v2/admin/backups/  — disparar backup on-demand (GAP-I2 fix)
"""
from django.urls import path
from .views import AdminBackupListView

app_name = 'admin_backups_v2'

urlpatterns = [
    path('backups/', AdminBackupListView.as_view(), name='backup-list'),
]
