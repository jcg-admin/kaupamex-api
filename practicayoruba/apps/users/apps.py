from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users'

    def ready(self):
        import apps.users.schema   # noqa: F401 — registra extensiones OpenAPI
        import apps.users.signals  # noqa: F401 — señales post_save
