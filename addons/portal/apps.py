"""AppConfig — addons.portal (Odoo portal)."""
from django.apps import AppConfig


class PortalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.portal'
    verbose_name = 'Portal — separación backoffice / cliente'
