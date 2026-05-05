from django.apps import AppConfig


class CatalogueConfig(AppConfig):
    def ready(self):
        import apps.catalogue.schema  # noqa: F401 — registra SPECTACULAR_TAGS
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.catalogue'
