"""AppConfig — addons.auto_backup (UC-ADM-05, Odoo app_auto_backup)."""
from django.apps import AppConfig


class AutoBackupConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.auto_backup'
    verbose_name = 'Auto Backup'
