"""AppConfig — ``addons.hr_homeworking``.

Mismo patrón que ``HrConfig``/``AccountFleetConfig``: las extensiones sobre
modelos ajenos (≙ ``_inherit``) se aplican en ``ready()``, cuando el
registro de modelos ya está poblado y ``add_to_class``/``setattr`` sobre una
clase ya definida no rompe con ``AppRegistryNotReady``.

El alta en ``INSTALLED_APPS`` es automática: ``LOCAL_APPS`` se deriva del
grafo de manifiestos (``config/settings/base.py``, ``_local_apps()``), y el
``depends: ['hr', 'base']`` de este addon lo ordena después de ``hr`` — que
es la precondición de sus extensiones (divergencia 3 de ``res_users.py``).
"""
import importlib

from django.apps import AppConfig


class HrHomeworkingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.hr_homeworking'
    label = 'hr_homeworking'
    verbose_name = 'Trabajo remoto (hr_homeworking)'

    #: Módulos que extienden modelos de OTROS addons — ≙ ``_inherit``. El
    #: nombre de cada archivo espeja el de la referencia
    #: (``odoo19c: hr_homeworking/models/*.py``); cada uno define su
    #: ``apply_hr_homeworking_<archivo>_extensions()`` (mismo criterio que
    #: ``HrConfig._EXTENSIONES``). ``hr_homeworking.py`` NO está aquí: es el
    #: modelo propio (``hr.employee.location``) y lo importa
    #: ``models/__init__.py`` por el camino normal de Django.
    _EXTENSIONES = {
        'addons.hr_homeworking.models.hr_employee':
            'apply_hr_homeworking_hr_employee_extensions',
        'addons.hr_homeworking.models.hr_employee_public':
            'apply_hr_homeworking_hr_employee_public_extensions',
        'addons.hr_homeworking.models.hr_work_location':
            'apply_hr_homeworking_hr_work_location_extensions',
        'addons.hr_homeworking.models.res_partner':
            'apply_hr_homeworking_res_partner_extensions',
        'addons.hr_homeworking.models.res_users':
            'apply_hr_homeworking_res_users_extensions',
    }

    def ready(self):
        """Cuelga las ubicaciones semanales sobre ``hr``/``base``.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4
        de ``no-lazy-imports.md``: llamada de función, no statement.
        """
        for module_path, function_name in self._EXTENSIONES.items():
            getattr(importlib.import_module(module_path), function_name)()
