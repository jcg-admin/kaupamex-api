import importlib

from django.apps import AppConfig


class AuthzTimeoutConfig(AppConfig):
    """Candado por tiempo de sesión — ≙ ``auth_timeout`` de la referencia.

    El addon no declara ningún modelo propio: su aporte entero son campos y
    métodos que cuelga de ``res.groups`` y ``res.users``. Por eso su única
    responsabilidad al arrancar es aplicar esas extensiones.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.authz_timeout'
    verbose_name = 'Autorización — Candado por tiempo de sesión'

    #: Extensiones que este addon cuelga de modelos ajenos — ≙ ``_inherit``.
    #: Mismo patrón que ``HrConfig._EXTENSIONES``: módulo → función, importado
    #: tarde desde ``ready()`` porque en tiempo de import el registro de
    #: modelos aún no está poblado (excepción #4 de ``no-lazy-imports``:
    #: llamada de función, no statement ``import``).
    _EXTENSIONES = {
        'addons.authz_timeout.models.res_groups':
            'apply_authz_timeout_res_groups_extensions',
        'addons.authz_timeout.models.res_users':
            'apply_authz_timeout_res_users_extensions',
    }

    def ready(self):
        """Aplica el candado sobre ``res.groups`` y su lectura en ``res.users``."""
        for module_path, function_name in self._EXTENSIONES.items():
            getattr(importlib.import_module(module_path), function_name)()
