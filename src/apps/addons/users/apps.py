from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.addons.users'
    # El registro de CsrfExemptSessionScheme (OpenApiAuthenticationExtension de
    # apps.addons.users.schema) lo garantiza el PREPROCESSING hook
    # config.spectacular_hooks.register_app_schema_extensions, que importa los
    # schema.py de las apps ANTES de generar el esquema (la resolucion del
    # securityScheme ocurre en la generacion, no en postprocesamiento). No se
    # usa ready() para no introducir un import lazy (check_no_lazy_imports).
    #
    # apps.addons.users.signals: eliminado (archivo borrado). La logica del unico
    # receiver (envio de email tras crear user inactivo) se movio inline a
    # RegisterSerializer.create con transaction.on_commit — simetria con
    # UC-AUTH-01 Alt-A.2 que tambien lo hace inline.
