"""Modelos del addon ``project_todo`` — un to-do es una tarea sin proyecto.

Adaptación de Odoo ``project_todo`` (``odoo19c: addons/project_todo/``,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Este addon **no declara modelos propios**: como la referencia, extiende los
que ya existen. Por eso aquí no se importa nada — sin modelo concreto no hay
clase que registrar en el import de la app.

- ``project_task.py`` espeja ``odoo19c: project_todo/models/project_task.py``
  y expone ``apply_project_todo_project_task_extensions()``, que
  ``ProjectTodoConfig.ready()`` invoca: el idioma de extensión cross-app ya
  establecido en este árbol (``project_account``, ``project_sms``,
  ``project_hr_skills``, ``hr_timesheet``).
- ``res_users.py`` espeja ``odoo19c: project_todo/models/res_users.py`` y es
  **documentación**: sus tres símbolos están bloqueados por piezas ausentes y
  medidas (el ``_get_activity_groups`` de ``mail``, el
  ``_onboard_users_into_project`` de ``project``, el compilador de QWeb). No
  exporta función ``apply_*`` y ``ready()`` no lo carga — ver su docstring
  para el desenlace de cada símbolo con su medición.
"""
