from django.apps import AppConfig


class SettingsAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.settings_app'
    verbose_name = 'Site Settings'

    def ready(self):
        import apps.settings_app.schema  # noqa: F401 — registra extensiones OpenAPI
