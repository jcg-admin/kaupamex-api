"""``project.project.stage`` — la plantilla de SMS de la etapa de proyecto.

Adaptación de Odoo project_sms/models/project_stage.py
(odoo-tools, odoo19c:, LGPL-3, 12 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 campo (medido por AST)
=====================================================

.. list-table::
   :header-rows: 1

   * - Símbolo de la referencia (línea)
     - Estado
   * - ``sms_template_id`` (Many2one ``sms.template``, ``:10-12``)
     - **Bloqueado por ``project.project.stage`` ausente** — el addon
       local ``project`` no portó las etapas de proyecto (medido:
       ``addons/project/models/`` sólo tiene ``project_project.py``,
       ``project_task.py`` y ``project_task_type.py``; ``Project`` no
       declara ``stage``). Sin el modelo no hay clase que extender.
       Condición de cierre: cuando ``project`` porte
       ``project.project.stage`` (y el campo ``Project.stage``), esta
       extensión es el gemelo exacto de ``project_task_type.py`` de este
       mismo addon — misma columna, mismo criterio.

Este módulo no registra nada: existe para espejar el árbol de la referencia
y dejar greppeable el bloqueo.
"""
