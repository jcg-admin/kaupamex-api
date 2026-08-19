"""``report.project.task.user`` — habilidades en el análisis de tareas.

Adaptación de Odoo project_hr_skills/report/report_project_task_user.py
(odoo-tools, odoo19c:, LGPL-3, 12 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 campo (medido por AST)
=====================================================

.. list-table::
   :header-rows: 1

   * - Símbolo de la referencia (línea)
     - Estado
   * - ``user_skill_ids``
       (One2many ``related='user_ids.employee_skill_ids'``, ``:12``)
     - **Bloqueado por ``report.project.task.user`` ausente** — el modelo
       base es una vista SQL de ``project`` (``project/report/
       project_report.py``, ``_auto = False`` + ``_table_query``) que el
       addon local ``project`` no portó (medido: ``addons/project/`` no
       tiene directorio ``report/`` ni clase ``ReportProjectTaskUser``).
       Sin la vista base no hay clase que extender. Cuando ``project``
       porte su reporte (como modelo Python con ``Meta.managed = False``,
       el criterio del CLAUDE.md de ``db`` para vistas), esta extensión es
       la misma propiedad que ``models/project_task.py`` ya cuelga sobre la
       tarea viva — condición de cierre del bloqueo.

Este módulo no registra nada: existe para espejar el árbol de la referencia
y dejar greppeable el bloqueo.
"""
