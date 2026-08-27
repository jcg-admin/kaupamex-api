"""AppConfig — ``addons.hr_fleet``.

Igual que ``AccountFleetConfig`` (el otro puente sobre ``fleet``, sin
modelos propios): la extensión se aplica en ``ready()``, cuando el registro
de modelos ya está poblado y ``add_to_class``/``setattr``/``chain_method``
sobre una clase ya definida no rompe con ``AppRegistryNotReady``.

El alta en ``INSTALLED_APPS`` es automática: ``LOCAL_APPS`` se deriva del
grafo de manifiestos (``config/settings/base.py``, ``_local_apps()``), y el
``depends: ['hr', 'fleet']`` de este addon lo ordena después de ambos.
"""
import importlib

from django.apps import AppConfig


class HrFleetConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.hr_fleet'
    label = 'hr_fleet'
    verbose_name = 'Puente Empleados ↔ Flota (hr_fleet)'

    #: Módulos que extienden modelos de OTROS addons — ≙ ``_inherit``. El
    #: nombre de cada archivo espeja el de la referencia
    #: (``odoo19c: hr_fleet/{models,wizard}/*.py``); cada uno define su
    #: ``apply_hr_fleet_<archivo>_extensions()`` (mismo criterio que
    #: ``HrConfig._EXTENSIONES``).
    _EXTENSIONES = {
        'addons.hr_fleet.models.employee':
            'apply_hr_fleet_employee_extensions',
        'addons.hr_fleet.models.fleet_vehicle':
            'apply_hr_fleet_fleet_vehicle_extensions',
        'addons.hr_fleet.models.fleet_vehicle_assignation_log':
            'apply_hr_fleet_fleet_vehicle_assignation_log_extensions',
        'addons.hr_fleet.models.fleet_vehicle_log_contract':
            'apply_hr_fleet_fleet_vehicle_log_contract_extensions',
        'addons.hr_fleet.models.fleet_vehicle_log_services':
            'apply_hr_fleet_fleet_vehicle_log_services_extensions',
        'addons.hr_fleet.models.fleet_vehicle_odometer':
            'apply_hr_fleet_fleet_vehicle_odometer_extensions',
        'addons.hr_fleet.models.ir_attachment':
            'apply_hr_fleet_ir_attachment_extensions',
        'addons.hr_fleet.models.mail_activity_plan_template':
            'apply_hr_fleet_mail_activity_plan_template_extensions',
        'addons.hr_fleet.wizard.hr_departure_wizard':
            'apply_hr_fleet_hr_departure_wizard_extensions',
    }

    def ready(self):
        """Cuelga el vínculo empleado ↔ vehículo sobre ``hr``/``fleet``.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4
        de ``no-lazy-imports.md``: llamada de función, no statement.
        """
        for module_path, function_name in self._EXTENSIONES.items():
            getattr(importlib.import_module(module_path), function_name)()
