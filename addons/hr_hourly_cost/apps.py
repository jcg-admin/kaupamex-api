"""AppConfig — ``addons.hr_hourly_cost``.

La extensión se aplica en ``ready()``, cuando el registro de modelos ya está
poblado y ``add_to_class`` sobre una clase ajena (``hr.HrEmployee``) no rompe
con ``AppRegistryNotReady``. Mismo criterio que ``product_expiry``/
``account_fleet``.
"""
import importlib

from django.apps import AppConfig


class HrHourlyCostConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.hr_hourly_cost'
    label              = 'hr_hourly_cost'
    verbose_name       = 'Costo por hora del empleado (hr_hourly_cost)'

    #: Un único módulo — cuelga ``hourly_cost`` sobre ``hr.HrEmployee``. Mismo
    #: patrón que ``AccountFleetConfig._EXTENSIONES``.
    _EXTENSIONES = (
        'addons.hr_hourly_cost.models.hr_employee',
    )

    def ready(self):
        """Cuelga ``hourly_cost`` sobre ``hr.HrEmployee``.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4
        de ``no-lazy-imports.md``: es una llamada de función, no un
        statement ``import``, así que el gate AST la deja pasar.
        """
        for ruta in self._EXTENSIONES:
            importlib.import_module(ruta).apply_hr_hourly_cost_extensions()
