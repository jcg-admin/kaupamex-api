"""AppConfig — ``addons.project_hr_skills``.

Puente Proyecto ↔ Habilidades, sin modelos propios: dos extensiones sobre
modelos ajenos (``project.task`` y ``res.users``), aplicadas en ``ready()``
cuando el registro de modelos ya está poblado (mismo patrón que
``HrFleetConfig``). El tercer archivo de la referencia
(``report/report_project_task_user.py``) está BLOQUEADO — ver ese módulo.
"""
import importlib

from django.apps import AppConfig


class ProjectHrSkillsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.project_hr_skills'
    label = 'project_hr_skills'
    verbose_name = 'Proyecto ↔ Habilidades (project_hr_skills)'

    #: Módulos que extienden modelos de OTROS addons — ≙ ``_inherit``. El
    #: nombre de cada archivo espeja el de la referencia
    #: (``odoo19c: project_hr_skills/models/*.py``). ``res_users`` va antes
    #: que ``project_task``: la propiedad de la tarea delega en la del
    #: usuario (el orden aquí sólo documenta la dependencia — la resolución
    #: real es en runtime).
    _EXTENSIONES = {
        'addons.project_hr_skills.models.res_users':
            'apply_project_hr_skills_res_users_extensions',
        'addons.project_hr_skills.models.project_task':
            'apply_project_hr_skills_project_task_extensions',
    }

    def ready(self):
        """Cuelga las habilidades del asignado sobre ``res.users`` y
        ``project.task``.

        ``importlib.import_module`` y no un ``import`` al top — excepción
        #4 de ``no-lazy-imports.md``: llamada de función, no statement.
        """
        for module_path, function_name in self._EXTENSIONES.items():
            getattr(importlib.import_module(module_path), function_name)()
