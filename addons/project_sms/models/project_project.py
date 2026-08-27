"""``project.project`` — el SMS al cliente cuando el proyecto cambia de etapa.

Adaptación de Odoo project_sms/models/project_project.py
(odoo-tools, odoo19c:, LGPL-3, 28 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Porte símbolo por símbolo — 3 métodos (medido por AST)
=======================================================

.. list-table::
   :header-rows: 1

   * - Símbolo de la referencia (línea)
     - Estado
   * - ``_send_sms`` (``:10-16``)
     - **Bloqueado por ``project.project.stage`` ausente** — la condición
       entera es ``project.stage_id.sms_template_id``, y ni el campo
       ``Project.stage`` ni el modelo de etapas de proyecto existen en el
       addon local ``project`` (ver ``project_stage.py`` de este addon,
       mismo bloqueo). Sin etapa no hay plantilla que resolver ni cambio
       de etapa que detectar.
   * - ``create`` (``:19-22``) / ``write`` (``:24-28``)
     - **Bloqueados por la misma pieza** — existen sólo para disparar
       ``_send_sms`` al crear y al cambiar ``stage_id``; el par de
       receptores ``pre_save``/``post_save`` que los materializaría (el
       patrón ya aplicado en ``project_task.py``) no tiene columna que
       vigilar.

Condición de cierre: cuando ``project`` porte ``project.project.stage`` y
``Project.stage``, este módulo se completa calcando ``project_task.py`` de
este mismo addon (receptores + ``_send_sms`` con ``self.partner`` directo,
que en el proyecto sí es campo propio).

Este módulo no registra nada: existe para espejar el árbol de la referencia
y dejar greppeable el bloqueo.
"""
