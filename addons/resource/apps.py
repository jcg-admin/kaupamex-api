from django.apps import AppConfig


class ResourceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.resource'
    verbose_name       = 'Recursos (calendarios de trabajo y disponibilidad)'
