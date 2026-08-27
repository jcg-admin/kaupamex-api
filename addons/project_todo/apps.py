"""AppConfig — ``addons.project_todo``.

Un solo módulo espeja ``odoo19c: project_todo/models/project_task.py`` y
cuelga su símbolo vivo sobre ``project.ProjectTask``. La extensión se aplica
en ``ready()``, cuando el registro de modelos ya está poblado y
``chain_method`` sobre una clase ajena no rompe con ``AppRegistryNotReady``
— mismo criterio que ``project_account`` / ``project_sms``.

``models/res_users.py`` **no** entra en ``_EXTENSIONES``: sus tres símbolos
están bloqueados (ver su docstring), así que no hay nada que colgar.
"""
import importlib

from django.apps import AppConfig


class ProjectTodoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.project_todo'
    label              = 'project_todo'
    verbose_name       = 'To-Do (project_todo)'

    #: Módulo → función. Mismo patrón que ``ProjectAccountConfig._EXTENSIONES``.
    _EXTENSIONES = {
        'addons.project_todo.models.project_task':
            'apply_project_todo_project_task_extensions',
    }

    def ready(self):
        """Cuelga sobre ``project.ProjectTask`` el nombrado del to-do.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4
        de ``no-lazy-imports.md``: es una llamada de función, no un statement
        ``import``, así que el gate AST la deja pasar.
        """
        for module_path, function_name in self._EXTENSIONES.items():
            getattr(importlib.import_module(module_path), function_name)()
