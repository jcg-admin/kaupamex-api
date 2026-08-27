"""``account.analytic.line`` — el apunte de hoja de horas (Odoo
``hr_timesheet``).

Adaptación de Odoo ``hr_timesheet/models/hr_timesheet.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 556 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia: 1 clase (``AccountAnalyticLine``,
``_inherit``), **13 campos**, **34 métodos** (incluye ``create``/``write``
sobrescritos). Símbolo por símbolo, ningún omitido en silencio.

Campos — 5 de 13 portados como columna real
==============================================

.. list-table::
   :header-rows: 1

   * - Campo de la referencia (línea)
     - Desenlace aquí
   * - ``task_id`` (``:62-65``)
     - **portado** — ``task`` (FK ``project.ProjectTask``). La referencia lo
       deriva por ``compute``/``domain`` de vista; aquí es escribible directo
       — sin motor de compute genérico (mismo criterio que
       ``account_bank_statement_line.py``), sincronizado en ``pre_save``
       (ver ``_sync_timesheet_derived_fields`` más abajo).
   * - ``project_id`` (``:67-69``)
     - **portado** — ``project`` (FK ``project.Project``), sincronizado
       desde ``task`` en el mismo receptor ``pre_save`` (≙
       ``_compute_project_id``/``_compute_task_id`` combinadas).
   * - ``employee_id`` (``:71-72``)
     - **portado** — ``employee`` (FK ``hr.HrEmployee``).
   * - ``department_id`` (``:74``)
     - **portado** — ``department`` (FK ``hr.HrDepartment``), sincronizado
       desde ``employee.department`` en el mismo receptor.
   * - ``manager_id`` (``:75``)
     - **portado** — ``manager`` (FK ``hr.HrEmployee``), sincronizado desde
       ``employee.parent`` en el mismo receptor.
   * - ``user_id`` (``:70``)
     - **BLOQUEADO — declarado, no un símbolo nuevo.** El campo ``user`` YA
       existe en ``AccountAnalyticLine`` (``api: addons/analytic/models/
       analytic_line.py``) con una decisión de diseño explícita: *"Sin
       default a env.user (esta API no acopla el modelo al usuario
       ambiental)"*. La referencia deriva ``user_id`` de
       ``employee_id.user_id`` por ``compute``; aplicar esa derivación aquí
       pisaría en silencio un valor que el llamador puede haber fijado a
       propósito. No se toca.
   * - ``job_title`` (``:73``)
     - **portado** — ``property`` delegada a ``employee.job_title``
       (``HrEmployee.job_title`` ya es una property — ``api: addons/hr/
       models/hr_employee.py:718-721``).
   * - ``parent_task_id`` (``:66``)
     - **BLOQUEADO** — ``related='task_id.parent_id'``. ``project.ProjectTask``
       de este árbol no declara jerarquía de subtareas (``grep -n
       "parent\\|child_ids" addons/project/models/project_task.py`` → 0
       hits): no hay ``parent`` del que derivar.
   * - ``encoding_uom_id`` (``:76``)
     - **BLOQUEADO** — deriva de ``company_id.timesheet_encode_uom_id``
       (``res.company``, portado en ``models/res_company.py`` de este mismo
       addon) vía sesión (``self.env.company``); sin ``env`` no hay compañía
       ambiental que resolver aquí.
   * - ``partner_id`` (``:77``)
     - **BLOQUEADO** — ``compute`` sobre ``task_id.partner_id``/
       ``project_id.partner_id``; ninguno de los dos existe en
       ``project.ProjectTask``/``project.Project`` de este árbol (0 hits).
   * - ``readonly_timesheet`` (``:78``)
     - **BLOQUEADO** — visibilidad por grupo de seguridad
       (``has_group('base.group_user')``); autorización aquí es por
       CAPACIDAD a nivel de vista DRF (``HasCapability``), no por campo.
   * - ``milestone_id`` (``:79``)
     - **BLOQUEADO** — ``project.milestone`` no existe en este árbol (0
       hits).
   * - ``message_partner_ids`` (``:80``) / ``_search_message_partner_ids``
     - **BLOQUEADO** — depende de ``mail.followers``, mecanismo de
       seguimiento de hilo no portado sobre ``project.project``/
       ``project.task``.
   * - ``calendar_display_name`` (``:81``)
     - **BLOQUEADO** — texto de UI para la vista de calendario
       (``self.env._``, i18n de sesión); sin consumidor de vista.

Métodos — desenlace por bloque
=================================

**Portados (mecanismo núcleo):**

- ``_hourly_cost`` (``:498-500``) — ``self.employee.hourly_cost or 0.0``.
- El cómputo de ``amount`` de ``_timesheet_postprocess_values``
  (``:445-475``) — reconstruido como parte del receptor ``pre_save``,
  simplificado (ver divergencia 1 abajo).

**BLOQUEADOS — sesión/entorno (``self.env``, ``has_group``, ``sudo``),
sin análogo en este stack:**

``_get_favorite_project_id_domain``, ``_get_favorite_project_id``,
``default_get``, ``_domain_project_id``, ``_domain_employee_id``,
``_search_message_partner_ids``, ``_compute_message_partner_ids``,
``_compute_display_name``, ``_is_readonly``, ``_compute_readonly_timesheet``,
``_compute_encoding_uom_id``, ``_compute_partner_id``, ``_compute_project_id``
(≙ el receptor ``pre_save``), ``_compute_task_id`` (ídem), ``_onchange_project_id``
(sin motor de onchange), ``_compute_user_id``, ``_compute_department_id``
(≙ el receptor ``pre_save``), ``_compute_calendar_display_name``,
``_check_can_write``, ``_check_can_create``, ``create``/``write``
(sobrescritos — la referencia resuelve ``employee_id`` desde el usuario
ambiental cuando falta; aquí el llamador lo declara explícito),
``get_views``, ``_timesheet_get_portal_domain``, ``_timesheet_preprocess_get_accounts``
(depende de ``_get_mandatory_plans``, mecanismo de planes analíticos
obligatorios no verificado en este pase), ``_timesheet_postprocess``,
``_timesheet_postprocess_values`` (reemplazado por el receptor),
``_is_timesheet_encode_uom_day``, ``_ensure_uom_hours``, ``_show_portal_timesheets``,
``action_open_timesheet_view_portal``, ``get_unusual_days``,
``get_import_templates``, ``get_views``.

**BLOQUEADOS — UOM/conversión, requieren seed de ``uom.product_uom_hour``/
``uom.product_uom_day`` (fuera del alcance de este agente, es data no
esquema):** ``_convert_hours_to_days``, ``_get_timesheet_time_day``,
``_split_amount_fname`` (depende de ``_split_amount_fname`` de la clase
base, no verificado en este pase).

**BLOQUEADO — trivial sin consumidor:** ``_get_report_base_filename``
(nombre de archivo de reporte; sin motor de reportes en el árbol),
``_default_user`` (sólo lo usaba ``_compute_user_id``, bloqueado).
``_is_updatable_timesheet`` — método de un solo ``return True``, sin
consumidor cableado (mismo criterio que ``web/models/ir_ui_menu.py::
load_web_menus`` citado en ``hr/models/ir_ui_menu.py``): se deja sin portar
en vez de fabricar un consumidor artificial.

Divergencias declaradas
==========================

1. **``amount`` — sin conversión de moneda.** La referencia calcula
   ``amount = -unit_amount * cost`` y luego lo convierte con
   ``employee_id.currency_id._convert(...)`` al de la cuenta analítica. Este
   puerto no tiene motor de conversión multi-moneda cableado sobre
   ``account.analytic.line``: el receptor deja ``amount = -unit_amount *
   hourly_cost`` sin convertir. Sucesor: cuando ``res.currency._convert``
   tenga un consumidor aquí, se cablea en el mismo receptor.
2. **Sin motor de compute genérico** — ``task``/``project``/``department``/
   ``manager`` se sincronizan con un receptor ``pre_save`` que replica el
   orden de dependencia de la referencia (``task`` → ``project``;
   ``employee`` → ``department``/``manager``), no con ``@api.depends``. Mismo
   patrón que ``account_bank_statement_line.py`` (``journal``/``company``
   denormalizados, sincronizados en ``save()``).
"""
from decimal import Decimal

import fields
import models
from django.db.models.signals import pre_save
from django.dispatch import receiver

from addons.analytic.models import AccountAnalyticLine
from addons.hr.models import HrDepartment, HrEmployee
from addons.project.models import Project, ProjectTask


def _add_if_absent(model, name, field):
    """Añade el campo sólo si el modelo no lo tiene ya.

    Idéntico al de ``account``/``account_fleet``/``product_expiry``: el
    idioma de extensión por ``add_to_class`` no tiene MRO, así que dos
    addons que cuelguen el mismo campo duplicarían la columna.
    """
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


def job_title(self):
    """≙ ``account.analytic.line.job_title`` — delegado al empleado
    (``odoo19c: hr_timesheet.py:73``, ``related='employee_id.job_title'``)."""
    return self.employee.job_title if self.employee_id else ''


def _hourly_cost(self):
    """≙ ``_hourly_cost`` (``odoo19c: hr_timesheet.py:498-500``)."""
    self_employee = self.employee
    if self_employee is None or self_employee.hourly_cost is None:
        return Decimal('0.00')
    return self_employee.hourly_cost


@receiver(pre_save, sender=AccountAnalyticLine,
          dispatch_uid='hr_timesheet.sync_timesheet_derived_fields')
def _sync_timesheet_derived_fields(sender, instance, **kwargs):
    """Sincroniza ``project``/``department``/``manager``/``amount`` desde
    ``task``/``employee`` — ≙ ``_compute_project_id`` + ``_compute_task_id``
    + ``_compute_department_id`` + fragmento de ``_timesheet_postprocess_values``
    (``odoo19c: hr_timesheet.py:138-165, 445-475``).

    Un ``pre_save`` corre en cada ``.save()``, que es el mismo disparador que
    ``@api.depends`` — sin el motor de dependencias que decide QUÉ recomputar,
    así que aquí se recomputa siempre que hay ``task``/``employee``. Ver
    divergencia 2 del docstring del módulo.
    """
    # ≙ _compute_project_id: si hay tarea con proyecto, el proyecto del
    # apunte se alinea al de la tarea. ≙ _compute_task_id (sin project no hay
    # task) NO se replica: limpiar `task` en cada save sin `project` sería
    # más agresivo que la referencia, que sólo reacciona al onchange de vista
    # de `project_id` — sin análogo aquí.
    if instance.task_id and instance.task.project_id:
        instance.project = instance.task.project

    if instance.employee_id:
        instance.department = instance.employee.department
        instance.manager = instance.employee.parent
        # ``unit_amount`` es Float (odoo19c: analytic_line.py); ``amount`` es
        # Decimal (fields.Monetary → DecimalField). Aritmética Decimal para
        # evitar el TypeError de mezclar float y Decimal directamente.
        instance.amount = -Decimal(str(instance.unit_amount)) * _hourly_cost(instance)


def apply_hr_timesheet_extensions():
    """Cuelga los 5 campos + la property sobre ``analytic.AccountAnalyticLine``.

    La llama ``HrTimesheetConfig.ready()``; los tests la invocan
    explícitamente (mismo criterio que ``account_fleet``).
    """
    _add_if_absent(AccountAnalyticLine, 'task', fields.Many2one(
        ProjectTask, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='timesheets',
        help_text='Odoo task_id. Tarea sobre la que se registra la hora.',
    ))
    _add_if_absent(AccountAnalyticLine, 'project', fields.Many2one(
        Project, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='timesheets',
        help_text='Odoo project_id. Proyecto sobre el que se registra la '
                  'hora — sincronizado desde task en pre_save cuando task '
                  'está presente.',
    ))
    _add_if_absent(AccountAnalyticLine, 'employee', fields.Many2one(
        HrEmployee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='timesheets',
        help_text='Odoo employee_id. Empleado que registra la hora — '
                  'define un hourly_cost en el empleado para valorizarla.',
    ))
    _add_if_absent(AccountAnalyticLine, 'department', fields.Many2one(
        HrDepartment, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='timesheets',
        help_text='Odoo department_id (compute, store=True) — sincronizado '
                  'desde employee.department en pre_save.',
    ))
    _add_if_absent(AccountAnalyticLine, 'manager', fields.Many2one(
        HrEmployee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='managed_timesheets',
        help_text='Odoo manager_id (related=employee_id.parent_id, '
                  'store=True) — sincronizado en pre_save.',
    ))
    if not hasattr(AccountAnalyticLine, 'job_title'):
        AccountAnalyticLine.job_title = property(job_title)
    if not hasattr(AccountAnalyticLine, '_hourly_cost'):
        AccountAnalyticLine._hourly_cost = _hourly_cost
