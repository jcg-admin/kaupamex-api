"""``hr_timesheet`` — Hoja de horas (Odoo ``hr_timesheet``, nombre público
"Task Logs").

Adaptación de Odoo ``hr_timesheet`` (``odoo-tools@622ddc2a``, ``odoo19c:``,
licencia ``LGPL-3`` declarada en su ``__manifest__.py``) — atribución y
aviso de licencia preservados (DEC-KX-03).

Qué es: cada empleado registra el tiempo dedicado a una tarea de proyecto
como un apunte analítico (``account.analytic.line``), valorizado con el
``hourly_cost`` del empleado (``hr_hourly_cost``, addon hermano portado en
este mismo pase). Cuelga sobre 12 modelos de 5 addons ajenos —
``hr.employee``, ``hr.employee.public``, ``account.analytic.line``,
``account.analytic.applicability``, ``project.project``, ``project.task``,
``project.update``, ``project.collaborator``, ``uom.uom``, ``res.company``,
``ir.http``, ``ir.ui.menu`` — y declara un modelo propio,
``account.analytic.line.calendar.employee``.

Medido contra la referencia (``odoo19c: addons/hr_timesheet/models/`` +
``wizard/``): **14 archivos de modelo + 1 de wizard = 15**, cada uno con
desenlace símbolo por símbolo en su propio docstring — 9 cuelgan vocabulario
real (``hr_timesheet.py``,
``hr_employee.py``, ``hr_employee_public.py``, ``project_project.py``,
``project_task.py``, ``res_company.py``, ``uom_uom.py``,
``analytic_applicability.py``, el modelo propio y el wizard parcial), 5
declaran no-op por mecanismo ausente o diferido (``ir_http.py``,
``ir_ui_menu.py``, ``project_collaborator.py``, ``project_update.py``,
``res_config_settings.py``).

Núcleo del mecanismo — ``models/hr_timesheet.py``
=====================================================

El apunte de hoja de horas cuelga 5 columnas nuevas sobre
``account.analytic.line`` (``task``, ``project``, ``employee``,
``department``, ``manager``) y un receptor ``pre_save`` que sincroniza
``project``/``department``/``manager`` desde ``task``/``employee`` y calcula
``amount = -unit_amount * hourly_cost`` — sin conversión de moneda (ver
divergencia declarada en ese módulo). Es el mismo patrón de "columna real +
sincronía en ``save()``, sin motor de compute genérico" que
``account_bank_statement_line.py`` ya estableció.

Instalación automática — sin wiring pendiente
================================================

``LOCAL_APPS`` se deriva del grafo de addons (``config/settings/base.py::
_local_apps``, recorre todo directorio bajo ``ADDONS_PATHS`` con
``__init__.py``). Este addon entra a ``INSTALLED_APPS`` sin que el
orquestador toque ``config/settings/base.py``.

Wiring pendiente (fuera del alcance de este agente):

1. **Migraciones de columna** en las apps DUEÑAS de cada modelo tocado —
   mismo criterio que ``account_fleet``/``l10n_mx``:

   - ``addons/analytic/migrations/`` — ``task``/``project``/``employee``/
     ``department``/``manager`` sobre ``AccountAnalyticLine``.
   - ``addons/hr/migrations/`` — ``has_timesheet`` es ``property``, sin
     columna, no requiere migración.
   - ``addons/project/migrations/`` — ``allow_timesheets``/
     ``allocated_hours`` sobre ``Project``.
   - ``addons/uom/migrations/`` — ``timesheet_widget`` sobre ``Uom``.
   - ``addons/base/migrations/`` — ``project_time_mode_id``/
     ``timesheet_encode_uom_id``/``internal_project_id`` sobre
     ``ResCompany``.
   - Este addon (``addons/hr_timesheet/migrations/``) — la tabla propia de
     ``AccountAnalyticLineCalendarEmployee``.

2. **Data de UOM** — ``project_time_mode_id``/``timesheet_encode_uom_id``
   resuelven ``Uom.objects.filter(name='Hours')`` (ver divergencia en
   ``models/res_company.py``); sin la fila semilla, el default resuelve
   ``None`` (campo nullable, no rompe).
"""
