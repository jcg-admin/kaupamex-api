from django.apps import AppConfig


class SettingsAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.settings_app'
    verbose_name = 'Site Settings'
    # def ready() removido: el import previo de apps.settings_app.schema
    # era redundante. config/spectacular_hooks.py:collect_app_tags ya
    # carga schema.py de cada app via importlib durante la generacion
    # del esquema OpenAPI.
