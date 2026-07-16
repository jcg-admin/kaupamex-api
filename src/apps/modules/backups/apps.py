"""AppConfig — apps.modules.backups (UC-ADM-05)."""
from django.apps import AppConfig


class BackupsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.modules.backups'
    verbose_name = 'Backups'
