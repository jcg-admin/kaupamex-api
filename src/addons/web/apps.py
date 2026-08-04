"""AppConfig — addons.web (familia ``web`` de la referencia)."""
from django.apps import AppConfig


class WebConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.web'
    verbose_name = 'Web — sesión del cliente'
