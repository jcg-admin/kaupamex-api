"""AppConfig — ``addons.hr_recruitment_skills``.

Puente Reclutamiento ↔ Habilidades: un modelo concreto propio
(``hr.applicant.skill``, importado por ``models/__init__.py``) más dos
extensiones sobre modelos ajenos (``hr.applicant`` y ``hr.job``), aplicadas
en ``ready()`` cuando el registro de modelos ya está poblado (mismo patrón
que ``HrFleetConfig``/``HrSkillsConfig``).
"""
import importlib

from django.apps import AppConfig


class HrRecruitmentSkillsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.hr_recruitment_skills'
    label = 'hr_recruitment_skills'
    verbose_name = 'Reclutamiento ↔ Habilidades (hr_recruitment_skills)'

    #: Módulos que extienden modelos de OTROS addons — ≙ ``_inherit``. El
    #: nombre de cada archivo espeja el de la referencia
    #: (``odoo19c: hr_recruitment_skills/models/*.py``).
    _EXTENSIONES = {
        'addons.hr_recruitment_skills.models.hr_applicant':
            'apply_hr_recruitment_skills_hr_applicant_extensions',
        'addons.hr_recruitment_skills.models.hr_job':
            'apply_hr_recruitment_skills_hr_job_extensions',
    }

    def ready(self):
        """Cuelga sobre ``hr.applicant`` y ``hr.job`` lo que este addon
        les añade.

        ``importlib.import_module`` y no un ``import`` al top — excepción
        #4 de ``no-lazy-imports.md``: llamada de función, no statement.
        """
        for module_path, function_name in self._EXTENSIONES.items():
            getattr(importlib.import_module(module_path), function_name)()
