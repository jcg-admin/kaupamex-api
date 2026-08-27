"""AppConfig — addons.authz_passkey (Odoo auth_passkey)."""
import importlib

from django.apps import AppConfig


class AuthzPasskeyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.authz_passkey'
    verbose_name = 'Autenticación — Passkeys (WebAuthn)'

    #: Extensiones que este addon cuelga de modelos ajenos — ≙ ``_inherit``.
    #: Mismo patrón que sus dos hermanos de la familia: módulo → función,
    #: importado tarde desde ``ready()`` porque en tiempo de import el registro
    #: de modelos aún no está poblado (excepción #4 de ``no-lazy-imports``:
    #: llamada de función, no statement ``import``).
    _EXTENSIONS = {
        'addons.authz_passkey.models.res_users':
            'apply_authz_passkey_res_users_extensions',
    }

    def ready(self):
        """Cuelga sobre ``res.users`` el eslabón de passkey de la cadena."""
        for module_path, function_name in self._EXTENSIONS.items():
            getattr(importlib.import_module(module_path), function_name)()
