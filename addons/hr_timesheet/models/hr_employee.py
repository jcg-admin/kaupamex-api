"""``hr.employee`` — indicador de hoja de horas (Odoo ``hr_timesheet``).

Adaptación de Odoo ``hr_timesheet/models/hr_employee.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 75 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia: 1 clase (``_inherit``), 1 campo
(``has_timesheet``), 4 métodos.

===================================  ====================================
Símbolo (línea)                      Desenlace
===================================  ====================================
``has_timesheet`` (:13)              **portado** — ``property``, consulta
                                      directa en vez de la subquery SQL de
                                      la referencia (ver abajo)
``_compute_has_timesheet`` (:15-29)  ídem — es la implementación de la
                                      property
``_compute_display_name`` (:32-46)   **BLOQUEADO** — depende de
                                      ``self.env.context['allowed_company_ids']``
                                      (sesión multi-compañía de vista); sin
                                      análogo.
``action_unlink_wizard`` (:49-57)    **BLOQUEADO** — acción de UI que abre
                                      un wizard (``hr.employee.delete.wizard``,
                                      portado en ``wizard/
                                      hr_employee_delete_wizard.py`` de este
                                      mismo addon); sin motor de acciones de
                                      cliente web.
``action_timesheet_from_employee``   **BLOQUEADO** — ídem, ``ir.actions.
(:59-64)``                           act_window`` por xmlid; sin cliente
                                      web ni sistema de acciones.
===================================  ====================================

``has_timesheet`` — divergencia de mecanismo
================================================

La referencia usa una subconsulta SQL cruda (``EXISTS(SELECT 1 FROM
account_analytic_line WHERE project_id IS NOT NULL AND employee_id = e.id)``)
para evitar cargar recordsets completos. Aquí es una propiedad Python que
consulta con el ORM (``.timesheets.filter(project__isnull=False).exists()``)
— usa el índice de la FK ``employee`` de ``account.analytic.line``
(colgada por ``models/hr_timesheet.py`` de este mismo addon, ``related_name=
'timesheets'``), semánticamente idéntico (``EXISTS`` vs ``.exists()``,
mismo plan de ejecución esperado en PostgreSQL).
"""
from addons.hr.models import HrEmployee


def has_timesheet(self):
    """≙ ``has_timesheet``/``_compute_has_timesheet`` (``odoo19c:
    hr_timesheet/models/hr_employee.py:13-29``). Ver docstring del módulo."""
    return self.timesheets.filter(project__isnull=False).exists()


def apply_hr_timesheet_hr_employee_extensions():
    """Cuelga ``has_timesheet`` sobre ``hr.HrEmployee``.

    La llama ``HrTimesheetConfig.ready()``.
    """
    if not hasattr(HrEmployee, 'has_timesheet'):
        HrEmployee.has_timesheet = property(has_timesheet)
