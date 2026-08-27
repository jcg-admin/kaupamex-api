"""
Admin URLs — addons.auto_backup (UC-ADM-05).

Montadas en config/urls.py bajo api/v2/admin/:

  GET  /api/v2/admin/backups/                    — historial paginado
  POST /api/v2/admin/backups/                    — disparar respaldo on-demand
  GET  /api/v2/admin/backups/download/<ruta>/    — descargar un archivo

La tercera es la contraparte de ``/dbbackup/download/<path:file_path>`` de
``app_auto_backup/controllers/main.py``; se monta bajo el prefijo del addon
en vez de en la raíz porque este árbol no tiene rutas de primer nivel por
addon — todas cuelgan de ``api/v2/``.
"""
from django.urls import path

from addons.auto_backup.controllers.main import (
    AdminBackupListView,
    BackupDownloadView,
)

app_name = 'admin_backups_v2'

urlpatterns = [
    path('backups/', AdminBackupListView.as_view(), name='backup-list'),
    path('backups/download/<path:file_path>/', BackupDownloadView.as_view(),
         name='backup-download'),
]
