"""AppConfig — ``addons.hr_recruitment_sms``.

Puente Reclutamiento ↔ SMS, sin modelos propios: una sola extensión sobre
``hr.applicant``, aplicada en ``ready()`` cuando el registro de modelos ya
está poblado (mismo patrón que ``HrFleetConfig``).
"""
import importlib

from django.apps import AppConfig


class HrRecruitmentSmsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.hr_recruitment_sms'
    label = 'hr_recruitment_sms'
    verbose_name = 'Reclutamiento ↔ SMS (hr_recruitment_sms)'

    #: Módulos que extienden modelos de OTROS addons — ≙ ``_inherit``. El
    #: nombre del archivo espeja el de la referencia
    #: (``odoo19c: hr_recruitment_sms/models/hr_applicant.py``).
    _EXTENSIONES = {
        'addons.hr_recruitment_sms.models.hr_applicant':
            'apply_hr_recruitment_sms_hr_applicant_extensions',
    }

    def ready(self):
        """Cuelga el envío de SMS sobre ``hr.applicant``.

        ``importlib.import_module`` y no un ``import`` al top — excepción
        #4 de ``no-lazy-imports.md``: llamada de función, no statement.
        """
        for module_path, function_name in self._EXTENSIONES.items():
            getattr(importlib.import_module(module_path), function_name)()
