from django.apps import AppConfig


class BaseSetupConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.base_setup'
    verbose_name = 'Ajustes generales (base_setup)'
