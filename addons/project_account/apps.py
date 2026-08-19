"""AppConfig — ``addons.project_account``.

Un módulo espeja ``odoo19c: project_account/models/project_project.py`` y
cuelga sus símbolos vivos sobre ``project.Project``. La extensión se aplica
en ``ready()``, cuando el registro de modelos ya está poblado y
``chain_method`` sobre una clase ajena no rompe con ``AppRegistryNotReady``
— mismo criterio que ``product_expiry`` / ``hr_timesheet``.
"""
import importlib

from django.apps import AppConfig


class ProjectAccountConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.project_account'
    label              = 'project_account'
    verbose_name       = 'Proyecto ↔ contabilidad (project_account)'

    #: Módulo → función. Mismo patrón que ``HrTimesheetConfig._EXTENSIONES``.
    _EXTENSIONES = {
        'addons.project_account.models.project_project':
            'apply_project_account_project_project_extensions',
    }

    def ready(self):
        """Cuelga el vocabulario contable del panel de rentabilidad sobre
        ``project.Project``.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4
        de ``no-lazy-imports.md``: es una llamada de función, no un statement
        ``import``, así que el gate AST la deja pasar.
        """
        for module_path, function_name in self._EXTENSIONES.items():
            getattr(importlib.import_module(module_path), function_name)()
