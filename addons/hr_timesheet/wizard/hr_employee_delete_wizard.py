"""``hr.employee.delete.wizard`` — confirmar el borrado de uno o más
empleados con hoja de horas (Odoo ``hr_timesheet``).

Adaptación de Odoo ``hr_timesheet/wizard/hr_employee_delete_wizard.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 63 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

``TransientModel`` → clase sin tabla con classmethods (patrón
``hr/wizard/hr_departure_wizard.py``): el estado del wizard (los empleados
seleccionados) lo pasa el llamador como argumento, no ``self.employee_ids``.

Porte símbolo por símbolo — 7 de la referencia
================================================

Medido por AST: 1 clase (``_name``/``_description``), 3 campos, 4 métodos.

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_name`` / ``_description`` (``:8-9``)
     - portados verbatim
   * - ``employee_ids`` (``:11``)
     - resuelto con otra forma — argumento ``employees`` de cada
       classmethod (el estado del wizard, no una columna)
   * - ``has_active_employee`` / ``_compute_has_active_employee``
       (``:13, 27-31``)
     - portado — ``has_active_employee(employees)``
   * - ``has_timesheet`` / ``_compute_has_timesheet`` (``:14, 16-25``)
     - portado — ``has_timesheet(employees)``, vía la ORM en vez de la
       subconsulta cruda de la referencia (mismo criterio que
       ``models/hr_employee.py`` de este mismo addon)
   * - ``action_archive`` (``:33-43``)
     - **BLOQUEADO** — delega en ``hr.departure.wizard`` (acción de UI,
       ``target: 'new'``); wizard hermano fuera del alcance de este pase.
   * - ``action_confirm_delete`` (``:45-49``)
     - portado — ``confirm_delete(employees)``
   * - ``action_open_timesheets`` (``:51-63``)
     - **BLOQUEADO** — acción de UI (``ir.actions.act_window``); sin
       cliente web ni sistema de acciones.
"""
from orm.models_transient import TransientModel

from addons.analytic.models import AccountAnalyticLine


class HrEmployeeDeleteWizard(TransientModel):
    """El asistente de borrado de empleados — ≙ ``hr.employee.delete.wizard``."""

    class Meta:
        abstract = True
        managed = False

    # ---- Atributos de clase de modelo — verbatim (``:8-9``) ----
    _name = 'hr.employee.delete.wizard'
    _description = 'Employee Delete Wizard'

    @classmethod
    def has_active_employee(cls, employees):
        """≙ ``has_active_employee``/``_compute_has_active_employee``
        (``odoo19c: hr_employee_delete_wizard.py:13, 27-31``)."""
        return any(employee.active for employee in employees)

    @classmethod
    def has_timesheet(cls, employees):
        """≙ ``has_timesheet``/``_compute_has_timesheet`` (``odoo19c:
        :14, 16-25``) — vía ORM en vez de la subconsulta cruda de la
        referencia (mismo criterio que ``models/hr_employee.py`` de este
        mismo addon)."""
        employee_ids = [employee.pk for employee in employees]
        if not employee_ids:
            return False
        return AccountAnalyticLine.objects.filter(
            employee_id__in=employee_ids,
        ).exists()

    @classmethod
    def confirm_delete(cls, employees):
        """≙ ``action_confirm_delete`` (``odoo19c: :45-49``), sin la
        acción de UI de retorno (``ir.actions.act_window``)."""
        for employee in employees:
            employee.delete()
