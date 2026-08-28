"""``project.project`` — vocabulario de hoja de horas (Odoo ``hr_timesheet``).

Adaptación de Odoo ``hr_timesheet/models/project_project.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 298 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST: 1 clase (``_inherit``), 12 campos, 21 métodos. La mayoría
depende de ``account_id`` (cuenta analítica del proyecto) e ``is_template``,
ninguno de los cuales existe en ``project.Project`` de este árbol (``grep -n
"account_id\\|is_template" addons/project/models/project_project.py`` → 0
hits) — es la misma ausencia que el propio docstring del puerto declara:
*"Se omite la analítica contable de Odoo (account.analytic.account),
inexistente en este stack (Clausula 5)"*.

Campos — 3 de 12 portados
============================

.. list-table::
   :header-rows: 1

   * - Campo de la referencia (línea)
     - Desenlace
   * - ``allow_timesheets`` (:13-15)
     - **portado** — columna real (``default=True``); la referencia lo
       deriva por ``compute`` de ``account_id`` (:46-49), ausente aquí —
       queda escribible directo, sin auto-apagado.
   * - ``timesheet_ids`` (:25)
     - **portado, sin columna propia** — es el reverso de
       ``AccountAnalyticLine.project`` (``related_name='timesheets'``,
       colgado en ``models/hr_timesheet.py`` de este mismo addon). Acceso:
       ``proyecto.timesheets``.
   * - ``allocated_hours`` (:34)
     - **portado** — columna real (``FloatField``, ``default=0.0``).
       ``tracking=True`` de la referencia queda **BLOQUEADO** — mismo
       criterio que ``hr_hourly_cost/models/hr_employee.py`` (ningún
       ``Field`` de este ORM acepta ``tracking=``).
   * - ``account_id`` (:16-22)
     - **BLOQUEADO** — ``account.analytic.account`` no está enlazado a
       ``project.Project`` en este árbol.
   * - ``analytic_account_active`` (:23)
     - **BLOQUEADO** — ``related='account_id.active'``; depende del
       anterior.
   * - ``timesheet_encode_uom_id`` (:26)
     - **BLOQUEADO** — deriva de ``company_id.timesheet_encode_uom_id``
       (sesión, ``self.env.company``) con fallback a la compañía del
       proyecto; sin ``env`` ambiental que resolver.
   * - ``total_timesheet_time`` (:27-29)
     - **BLOQUEADO** — requiere conversión de unidades (UOM factor +
       ``encode_uom_in_days``); ver divergencia del módulo hermano
       ``models/hr_timesheet.py`` sobre UOM (seed de datos fuera de
       alcance).
   * - ``encode_uom_in_days`` (:30)
     - **BLOQUEADO** — ídem, depende de la compañía ambiental.
   * - ``is_internal_project`` (:31)
     - **BLOQUEADO** — depende de ``company_id.internal_project_id``
       (portado como columna en ``models/res_company.py`` de este mismo
       addon) comparado contra ``self`` — es comparación directa de PK,
       portable en principio, pero requiere resolver la compañía del
       proyecto: ``project.Project`` de este árbol tiene ``company``
       (FK opcional). **Diferido** por prioridad (mecanismo núcleo
       primero); no depende de sesión, así que es candidato limpio para un
       pase siguiente.
   * - ``remaining_hours`` / ``is_project_overtime`` (:32-33)
     - **portados** — ``property`` que resta ``allocated_hours`` menos la
       suma de ``timesheets.unit_amount`` (agregación ORM directa, sin
       UOM — ver divergencia).
   * - ``effective_hours`` (:35)
     - **portado** — ``property``, la misma agregación.

Métodos — todos BLOQUEADOS
============================

``_compute_encode_uom_in_days``, ``_compute_timesheet_encode_uom_id``,
``_compute_allow_timesheets``, ``_compute_is_internal_project``,
``_search_is_internal_project``, ``_compute_remaining_hours``,
``_search_is_project_overtime``, ``_check_allow_timesheet``,
``_compute_total_timesheet_time``, ``create``/``write`` (sobrescritos —
crean/reutilizan la cuenta analítica, ausente), ``_compute_display_name``
(sesión multi-compañía), ``_init_data_analytic_account``,
``_unlink_except_contains_entries`` (``RedirectWarning``, UI),
``get_create_edit_project_ids``, ``_convert_project_uom_to_timesheet_encode_uom``
(UOM + sesión), ``action_project_timesheets`` (acción de UI),
``_get_processed_analytic_account_vals``, ``_get_stat_buttons`` (botones de
UI), ``action_view_tasks`` (acción de UI), ``_toggle_template_mode``
(``is_template`` ausente). Todos dependen de mecanismos ya declarados
ausentes (cuenta analítica, sesión, UI/acciones, UOM) — no hay uno nuevo que
justifique una tabla aparte.

Divergencia — ``effective_hours``/``remaining_hours`` sin UOM
==================================================================

La referencia convierte ``unit_amount`` a la unidad de codificación de la
compañía antes de sumar (``total_timesheet_time``); aquí se suma
``unit_amount`` directo (las horas registradas, sin convertir). Es
equivalente cuando la unidad de codificación es "Horas" (el default de
``res.company`` en este mismo addon, ``models/res_company.py``); diverge si
la compañía usa "Días". Documentado, no oculto.
"""
import fields
import models

from addons.project.models import Project


def _add_if_absent(model, name, field):
    """Idéntico al de ``models/hr_timesheet.py`` de este mismo addon."""
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


def _effective_hours(self):
    """≙ ``effective_hours``/``_compute_remaining_hours`` (``odoo19c:
    hr_timesheet/models/project_project.py:35, 68-79``), sin UOM — ver
    docstring del módulo."""
    total = self.timesheets.aggregate(total=models.Sum('unit_amount'))['total']
    return round(total, 2) if total else 0.0


def _remaining_hours(self):
    """≙ ``remaining_hours`` (``odoo19c: :32, 68-79``)."""
    return self.allocated_hours - _effective_hours(self)


def _is_project_overtime(self):
    """≙ ``is_project_overtime`` (``odoo19c: :33, 68-79``)."""
    return _remaining_hours(self) < 0


def apply_hr_timesheet_project_project_extensions():
    """Cuelga los 3 campos + 3 properties sobre ``project.Project``.

    La llama ``HrTimesheetConfig.ready()``.
    """
    _add_if_absent(Project, 'allow_timesheets', fields.Boolean(
        default=True,
        help_text='Odoo allow_timesheets. La referencia lo apaga cuando no '
                  'hay cuenta analítica (account_id); ausente aquí — queda '
                  'escribible directo.',
    ))
    _add_if_absent(Project, 'allocated_hours', fields.Float(
        default=0.0,
        help_text='Odoo allocated_hours. BLOQUEADO por ``el motor de '
                  'tracking`` — tracking=True lo exige; ver '
                  'docstring del módulo.',
    ))
    for name, function in (
        ('effective_hours', _effective_hours),
        ('remaining_hours', _remaining_hours),
        ('is_project_overtime', _is_project_overtime),
    ):
        if not hasattr(Project, name):
            setattr(Project, name, property(function))
