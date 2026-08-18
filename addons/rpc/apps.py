from django.apps import AppConfig


class RpcConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.rpc'
    verbose_name       = 'Despacho genérico por modelo y método'
