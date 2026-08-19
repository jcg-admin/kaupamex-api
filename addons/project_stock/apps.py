"""AppConfig — ``addons.project_stock``.

Dos módulos espejan ``odoo19c: project_stock/models/*.py`` en el orden en que
la referencia los importa. La extensión se aplica en ``ready()``, cuando el
registro de modelos ya está poblado y ``add_field_if_absent``/``chain_method``
sobre una clase ajena no rompe con ``AppRegistryNotReady`` — mismo criterio
que ``product_expiry`` / ``hr_timesheet``.
"""
import importlib

from django.apps import AppConfig


class ProjectStockConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.project_stock'
    label              = 'project_stock'
    verbose_name       = 'Proyecto ↔ inventario (project_stock)'

    #: Módulo → función. Mismo patrón que ``HrTimesheetConfig._EXTENSIONES``.
    _EXTENSIONES = {
        'addons.project_stock.models.project_project':
            'apply_project_stock_project_project_extensions',
        'addons.project_stock.models.stock_picking':
            'apply_project_stock_stock_picking_extensions',
    }

    def ready(self):
        """Cuelga la FK ``project`` sobre ``stock.picking`` y la capacidad de
        filtrado sobre ``project.Project``.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4
        de ``no-lazy-imports.md``: es una llamada de función, no un statement
        ``import``, así que el gate AST la deja pasar.
        """
        for module_path, function_name in self._EXTENSIONES.items():
            getattr(importlib.import_module(module_path), function_name)()
