from django.apps import AppConfig


class CatalogueConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.addons.catalogue'
    # def ready() removido: el import previo de apps.addons.catalogue.schema
    # era redundante. config/spectacular_hooks.py:collect_app_tags ya
    # carga schema.py de cada app via importlib durante la generacion
    # del esquema OpenAPI (esta wired en POSTPROCESSING_HOOKS de
    # SPECTACULAR_SETTINGS en config/settings/base.py:187).
