"""``project.task`` — vocabulario de hoja de horas (Odoo ``hr_timesheet``).

Adaptación de Odoo ``hr_timesheet/models/project_task.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 291 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST: 1 clase (``_inherit``), 12 campos + 1 constante de módulo
(``PROJECT_TASK_READABLE_FIELDS``), 21 métodos. El porte es el más delgado
de los cinco archivos de este addon porque ``project.ProjectTask`` de este
árbol no declara **ni** ``allocated_hours`` (lo asume ya declarado por
``project``, que no lo porta — ver docstring del propio archivo: *"Se omite
la maquinaria de horas/timesheets/recurrencia de Odoo … no existe en este
stack"*) **ni** jerarquía de subtareas (``parent``/``child_ids`` — ``grep -n
"parent\\|child_ids" addons/project/models/project_task.py`` → 0 hits).

Campos — 2 de 12 portados
============================

.. list-table::
   :header-rows: 1

   * - Campo de la referencia (línea)
     - Desenlace
   * - ``timesheet_ids`` (:45)
     - **portado, sin columna propia** — reverso de
       ``AccountAnalyticLine.task`` (``related_name='timesheets'``, colgado
       en ``models/hr_timesheet.py`` de este mismo addon). Acceso:
       ``tarea.timesheets``.
   * - ``allow_timesheets`` (:34-37)
     - **portado** — ``property`` delegada a ``project.allow_timesheets``
       (mismo campo colgado en ``models/project_project.py`` de este
       addon).
   * - ``effective_hours`` (:40)
     - **portado** — ``property``, suma ``timesheets.unit_amount``.
   * - ``project_id`` (:32, redeclaración de dominio de vista)
     - **BLOQUEADO** — el ``domain=`` es metadata de formulario del
       cliente web; sin vista que la consuma.
   * - ``analytic_account_active`` (:33)
     - **BLOQUEADO** — depende de ``project_id.analytic_account_active``,
       a su vez bloqueado en ``models/project_project.py`` (sin cuenta
       analítica).
   * - ``remaining_hours`` (:38) / ``remaining_hours_percentage`` (:39)
     - **BLOQUEADO** — dependen de ``allocated_hours``, ausente en
       ``project.ProjectTask`` de este árbol (no lo declara ``project`` ni
       lo declararía este addon — pertenece al alcance de ``project``, no
       de ``hr_timesheet``).
   * - ``total_hours_spent`` (:41) / ``progress`` (:42) / ``overtime``
       (:43) / ``subtask_effective_hours`` (:44)
     - **BLOQUEADO** — dependen de ``allocated_hours`` y/o de
       ``child_ids`` (subtareas), ambos ausentes.
   * - ``encode_uom_in_days`` (:46)
     - **BLOQUEADO** — sesión (``self.env.company``), mismo criterio que
       el campo homónimo de ``models/project_project.py``.
   * - ``display_name`` (:47-55, sólo cambia el ``help``)
     - **BLOQUEADO** — el override sólo redeclara el texto de ayuda de un
       campo ya existente en la clase base; sin cliente web que lo
       muestre, no aporta.
   * - ``PROJECT_TASK_READABLE_FIELDS`` (constante, :13-26)
     - **BLOQUEADO** — lista blanca de campos expuestos al portal de
       clientes; sin portal en este stack.

Métodos — todos BLOQUEADOS
============================

``TASK_PORTAL_READABLE_FIELDS`` (portal), ``_check_project_root``
(``self.env['account.analytic.line'].sudo()``, sesión), ``_uom_in_days``/
``_compute_encode_uom_in_days`` (sesión), ``_compute_allow_timesheets``/
``_search_allow_timesheets`` (reemplazados por la property portada),
``_compute_effective_hours`` (ídem), ``_compute_progress_hours``,
``_compute_remaining_hours_percentage``, ``_search_remaining_hours_percentage``,
``_compute_remaining_hours``, ``_compute_total_hours_spent``,
``_compute_subtask_effective_hours`` (todos dependen de ``allocated_hours``/
``child_ids``, ausentes), ``_get_group_pattern``/``_prepare_pattern_groups``/
``_get_cannot_start_with_patterns``/``_extract_allocated_hours``/
``_get_groups`` (parser de patrones del título de tarea del cliente web —
sin análogo), ``action_view_subtask_timesheet`` (acción de UI),
``_get_timesheet``/``_get_timesheet_report_data`` (reportes, sin motor),
``_compute_display_name`` (sesión), ``_unlink_except_contains_entries``
(``RedirectWarning``, UI), ``_convert_hours_to_days`` (UOM + sesión),
``_get_portal_total_hours_dict`` (portal).
"""
import models

from addons.project.models import ProjectTask


def allow_timesheets(self):
    """≙ ``allow_timesheets``/``_compute_allow_timesheets`` (``odoo19c:
    hr_timesheet/models/project_task.py:34-37, 72-75``)."""
    return bool(self.project_id and self.project.allow_timesheets)


def effective_hours(self):
    """≙ ``effective_hours``/``_compute_effective_hours`` (``odoo19c:
    :40, 83-92``)."""
    total = self.timesheets.aggregate(total=models.Sum('unit_amount'))['total']
    return round(total, 2) if total else 0.0


def apply_hr_timesheet_project_task_extensions():
    """Cuelga 2 properties sobre ``project.ProjectTask``.

    La llama ``HrTimesheetConfig.ready()``.
    """
    for name, function in (
        ('allow_timesheets', allow_timesheets),
        ('effective_hours', effective_hours),
    ):
        if not hasattr(ProjectTask, name):
            setattr(ProjectTask, name, property(function))
