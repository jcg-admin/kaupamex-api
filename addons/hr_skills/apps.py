import importlib

from django.apps import AppConfig


class HrSkillsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.hr_skills'
    verbose_name       = ('Habilidades (hr.skill.type, hr.skill, '
                          'hr.employee.skill, hr.job.skill, hr.resume.line)')

    #: Extensiones que hr_skills cuelga de modelos ajenos — ≙ `_inherit` de
    #: la referencia. Mismo patrón que `HrConfig._EXTENSIONES` (renombrado
    #: en inglés aquí — identificador nuevo, ver
    #: `.claude/rules/identificadores-en-ingles.md`): módulo → función,
    #: importado tarde desde `ready()` porque en tiempo de import el
    #: registro de modelos aún no está poblado (excepción #4 de
    #: `no-lazy-imports`: llamada de función, no statement `import`).
    _EXTENSIONS = {
        'addons.hr_skills.models.hr_employee': 'apply_hr_skills_hr_employee_extensions',
        'addons.hr_skills.models.hr_employee_public': 'apply_hr_skills_hr_employee_public_extensions',
        'addons.hr_skills.models.hr_job': 'apply_hr_skills_hr_job_extensions',
        'addons.hr_skills.models.resource_resource': 'apply_hr_skills_resource_resource_extensions',
    }

    def ready(self):
        """Aplica lo que hr_skills cuelga de modelos ajenos (hr.employee,
        hr.employee.public, hr.job, resource.resource)."""
        for module_path, function_name in self._EXTENSIONS.items():
            getattr(importlib.import_module(module_path), function_name)()
