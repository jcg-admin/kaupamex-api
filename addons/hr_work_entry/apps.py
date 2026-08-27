import importlib

from django.apps import AppConfig


class HrWorkEntryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.hr_work_entry'
    verbose_name       = 'Entradas de trabajo (hr.work.entry)'

    #: Extensiones que hr_work_entry cuelga de modelos ajenos — ≙ ``_inherit``
    #: de la referencia. Mismo patrón que ``HrConfig._EXTENSIONES``: módulo →
    #: función, importado tarde desde ``ready()`` porque en tiempo de import
    #: el registro de modelos aún no está poblado (excepción #4 de
    #: ``no-lazy-imports``: llamada de función, no statement ``import``).
    _EXTENSIONES = {
        'addons.hr_work_entry.models.hr_employee':
            'apply_hr_work_entry_hr_employee_extensions',
        'addons.hr_work_entry.models.hr_version':
            'apply_hr_work_entry_hr_version_extensions',
        'addons.hr_work_entry.models.resource_calendar':
            'apply_hr_work_entry_resource_calendar_extensions',
        'addons.hr_work_entry.models.resource_calendar_attendance':
            'apply_hr_work_entry_resource_calendar_attendance_extensions',
        'addons.hr_work_entry.models.resource_calendar_leaves':
            'apply_hr_work_entry_resource_calendar_leaves_extensions',
    }

    def ready(self):
        """Aplica lo que este addon cuelga de modelos ajenos (hr, resource)."""
        for module_path, function_name in self._EXTENSIONES.items():
            getattr(importlib.import_module(module_path), function_name)()
