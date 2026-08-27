"""AppConfig — ``addons.account_peppol_advanced_fields``.

Un módulo espeja ``odoo19c: account_peppol_advanced_fields/models/
account_move.py`` y cuelga sus siete campos sobre ``account.AccountMove``. La
extensión se aplica en ``ready()``, cuando el registro de modelos ya está
poblado y ``add_field_if_absent`` sobre una clase ajena no rompe con
``AppRegistryNotReady`` — mismo criterio que ``account_peppol`` /
``project_account``.
"""
import importlib

from django.apps import AppConfig


class AccountPeppolAdvancedFieldsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.account_peppol_advanced_fields'
    label              = 'account_peppol_advanced_fields'
    verbose_name       = 'Peppol — referencias avanzadas [DEPRECATED]'

    #: Módulo → función. Mismo patrón que ``AccountPeppolConfig._EXTENSIONES``.
    _EXTENSIONES = {
        'addons.account_peppol_advanced_fields.models.account_move':
            'apply_account_peppol_advanced_fields_account_move_extensions',
    }

    def ready(self):
        """Cuelga las siete referencias documentales sobre ``account.move``.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4
        de ``no-lazy-imports.md``: es una llamada de función, no un statement
        ``import``, así que el gate AST la deja pasar.
        """
        for module_path, function_name in self._EXTENSIONES.items():
            getattr(importlib.import_module(module_path), function_name)()
