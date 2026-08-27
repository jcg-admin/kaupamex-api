"""AppConfig — addons.authz_signup (Odoo auth_signup)."""
import importlib

from django.apps import AppConfig


class AuthSignupConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.authz_signup'
    verbose_name = 'Autenticación — Auto-registro y reset'

    def ready(self):
        """Registra las señales que cancelan el signup pendiente.

        ``importlib`` y no ``import``: el checker prohíbe el statement dentro
        de una función y el lift al top rompe ``django.setup()``
        (``AppRegistryNotReady``). Excepción #4 de ``no-lazy-imports.md``.
        """
        importlib.import_module('addons.authz_signup.models.signals')
