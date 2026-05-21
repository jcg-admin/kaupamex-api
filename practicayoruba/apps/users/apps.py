from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users'
    # def ready() removido:
    # - apps.users.schema: redundante. config/spectacular_hooks.py:
    #   collect_app_tags ya lo carga via importlib durante la
    #   generacion del esquema OpenAPI.
    # - apps.users.signals: eliminado (archivo borrado). La logica del
    #   unico receiver (envio de email tras crear user inactivo) se
    #   movio inline a RegisterSerializer.create con transaction.
    #   on_commit — simetria con UC-AUTH-01 Alt-A.2 que tambien lo
    #   hace inline.
