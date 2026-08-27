"""AppConfig — ``addons.project_sms``.

Puente Proyecto ↔ SMS, sin modelos propios: una extensión de campo sobre
``project.task.type`` y el disparo de SMS al mover de etapa una tarea
(``project_task.py``), aplicadas en ``ready()`` cuando el registro de
modelos ya está poblado (mismo patrón que ``HrFleetConfig``).

Las otras dos piezas de la referencia están BLOQUEADAS y por eso no figuran
en ``_EXTENSIONES``: ``project_stage.py`` y ``project_project.py`` dependen
del modelo ``project.project.stage``, no portado por el addon local
``project`` (ver los docstrings de esos módulos).
"""
import importlib

from django.apps import AppConfig


class ProjectSmsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.project_sms'
    label = 'project_sms'
    verbose_name = 'Proyecto ↔ SMS (project_sms)'

    #: Módulos que extienden modelos de OTROS addons — ≙ ``_inherit``. El
    #: nombre de cada archivo espeja el de la referencia
    #: (``odoo19c: project_sms/models/*.py``).
    _EXTENSIONES = {
        'addons.project_sms.models.project_task_type':
            'apply_project_sms_project_task_type_extensions',
        'addons.project_sms.models.project_task':
            'apply_project_sms_project_task_extensions',
    }

    def ready(self):
        """Cuelga la plantilla de SMS sobre la etapa y el disparo sobre la
        tarea.

        ``importlib.import_module`` y no un ``import`` al top — excepción
        #4 de ``no-lazy-imports.md``: llamada de función, no statement.
        """
        for module_path, function_name in self._EXTENSIONES.items():
            getattr(importlib.import_module(module_path), function_name)()
