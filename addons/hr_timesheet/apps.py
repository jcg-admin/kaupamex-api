"""AppConfig — ``addons.hr_timesheet``.

Doce módulos espejan ``odoo19c: hr_timesheet/models/*.py`` (el treceavo,
``account_analytic_line_calendar_employee.py``, declara un modelo **propio**
y lo importa ``models/__init__.py``, no ``ready()``) — cinco cuelgan símbolos
reales, siete son no-op declarado (mecanismo ausente o diferido). La
extensión se aplica en ``ready()``, cuando el registro de modelos ya está
poblado y ``add_to_class``/``chain_method``/``setattr`` sobre una clase ajena
no rompe con ``AppRegistryNotReady``. Mismo criterio que
``product_expiry``/``account_fleet``.

Orden — ``hr_employee`` antes que ``hr_employee_public``
============================================================

``models/hr_employee_public.py::apply_hr_timesheet_hr_employee_public_extensions``
delega en ``HrEmployee.has_timesheet``, colgado por
``models/hr_employee.py`` — el orden de ``_EXTENSIONES`` fija esa
precedencia.
"""
import importlib

from django.apps import AppConfig


class HrTimesheetConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.hr_timesheet'
    label              = 'hr_timesheet'
    verbose_name       = 'Hoja de horas (hr_timesheet)'

    #: Módulo → función. Cada uno define ``apply_hr_timesheet_*_extensions``.
    #: Mismo patrón que ``HrConfig._EXTENSIONES``/``ProductExpiryConfig``.
    _EXTENSIONES = {
        'addons.hr_timesheet.models.analytic_applicability':
            'apply_hr_timesheet_analytic_applicability_extensions',
        'addons.hr_timesheet.models.hr_employee':
            'apply_hr_timesheet_hr_employee_extensions',
        'addons.hr_timesheet.models.hr_employee_public':
            'apply_hr_timesheet_hr_employee_public_extensions',
        'addons.hr_timesheet.models.hr_timesheet':
            'apply_hr_timesheet_extensions',
        'addons.hr_timesheet.models.ir_http':
            'apply_hr_timesheet_ir_http_extensions',
        'addons.hr_timesheet.models.ir_ui_menu':
            'apply_hr_timesheet_ir_ui_menu_extensions',
        'addons.hr_timesheet.models.project_collaborator':
            'apply_hr_timesheet_project_collaborator_extensions',
        'addons.hr_timesheet.models.project_project':
            'apply_hr_timesheet_project_project_extensions',
        'addons.hr_timesheet.models.project_task':
            'apply_hr_timesheet_project_task_extensions',
        'addons.hr_timesheet.models.project_update':
            'apply_hr_timesheet_project_update_extensions',
        'addons.hr_timesheet.models.res_company':
            'apply_hr_timesheet_res_company_extensions',
        'addons.hr_timesheet.models.res_config_settings':
            'apply_hr_timesheet_res_config_settings_extensions',
        'addons.hr_timesheet.models.uom_uom':
            'apply_hr_timesheet_uom_uom_extensions',
    }

    def ready(self):
        """Cuelga el vocabulario de hoja de horas sobre ``hr``/``analytic``/
        ``project``/``uom``/``base.ResCompany``.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4
        de ``no-lazy-imports.md``: es una llamada de función, no un
        statement ``import``, así que el gate AST la deja pasar.
        """
        for ruta, function_name in self._EXTENSIONES.items():
            getattr(importlib.import_module(ruta), function_name)()
