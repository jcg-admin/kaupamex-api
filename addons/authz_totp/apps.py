"""AppConfig — addons.authz_totp (Odoo auth_totp)."""
import importlib

from django.apps import AppConfig


class AuthTotpConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.authz_totp'
    verbose_name = 'Autenticación — 2FA (TOTP)'

    #: Extensiones que este addon cuelga de modelos ajenos — ≙ ``_inherit``.
    #: Mismo patrón que ``AuthzTimeoutConfig._EXTENSIONES``: módulo → función,
    #: importado tarde desde ``ready()`` porque en tiempo de import el registro
    #: de modelos aún no está poblado (excepción #4 de ``no-lazy-imports``:
    #: llamada de función, no statement ``import``).
    _EXTENSIONS = {
        'addons.authz_totp.models.res_users':
            'apply_authz_totp_res_users_extensions',
    }

    def ready(self):
        """Cuelga sobre ``res.users`` el eslabón medio de la cadena de MFA."""
        for module_path, function_name in self._EXTENSIONS.items():
            getattr(importlib.import_module(module_path), function_name)()
