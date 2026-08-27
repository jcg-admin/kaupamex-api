"""``report.project.task.user`` — el informe de tareas, con el tiempo que le
queda a su pedido (Odoo ``sale_timesheet``).

Adaptación de Odoo ``sale_timesheet/report/project_report.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 24 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia: 1 clase (``ReportProjectTaskUser``,
``_inherit``), **1 campo**, **3 métodos**. **No-op medido** — 0 de 4, por la
misma razón de SITIO que ``report/timesheets_analysis_report.py``.

Por qué este archivo no declara ningún modelo
================================================

El informe base **no existe en este árbol**: ``report.project.task.user`` lo
declara ``project`` (``odoo19c: addons/project/report/project_report.py``), y
el puerto de ``project`` aquí tiene tres archivos de modelo
(``project_project.py``, ``project_task.py``, ``project_task_type.py``) y
ningún directorio ``report/`` — medido: 0 hits de ``ReportProjectTaskUser`` y
de ``report.project.task.user`` en ``addons/`` y ``src/``.

``sale_timesheet`` sólo lo **extiende**: le añade una columna y tres
fragmentos de SQL. Declarar aquí el informe entero lo pondría en el hogar
equivocado (``H-API-568`` / ``H-API-578``).

Sucesor: tarea PENDIENTE DE ASIGNAR — portar
``project/report/project_report.py`` como modelo ``managed=False`` en
``addons/project/report/``, con su vista SQL creada por migración (precedente:
``api: addons/hr/models/hr_employee_public.py:214``).

Porte símbolo por símbolo — 0 de 4
=====================================

.. list-table::
   :header-rows: 1

   * - Símbolo de la referencia (línea)
     - Desenlace aquí
   * - ``remaining_hours_so`` (:9)
     - **BLOQUEADO** por dos piezas: el informe base (arriba) y
       ``sale.order.line.remaining_hours``, que declara este mismo addon en
       ``models/sale_order_line.py`` y allí queda bloqueado por
       ``qty_delivered`` (``addons/sale``). Su ``groups=
       "hr_timesheet.group_hr_timesheet_user"`` es visibilidad por grupo, que
       aquí es autorización por CAPACIDAD a nivel de vista DRF.
   * - ``_select`` (:11-15) / ``_group_by`` (:17-21) / ``_from`` (:23-24)
     - **BLOQUEADOS** — los tres son fragmentos de SQL que se concatenan a los
       del informe base. Sin el informe base no hay a qué concatenarlos; y el
       ``LEFT JOIN sale_order_line sol ON t.sale_line_id = sol.id`` de
       ``_from`` necesita ``project_task.sale_line_id``, que declara
       ``sale_project`` (``odoo19c: sale_project/models/project_task.py:26``)
       y da 0 hits aquí.
"""


def apply_sale_timesheet_project_report_extensions():
    """No-op declarado — el informe base no existe en este árbol. Ver el
    docstring del módulo.

    Se conserva la función (y su entrada en
    ``SaleTimesheetConfig._EXTENSIONES``) porque es el punto exacto donde se
    cuelga la columna el día que ``project`` porte su informe.
    """
    return None


__all__ = ['apply_sale_timesheet_project_report_extensions']
