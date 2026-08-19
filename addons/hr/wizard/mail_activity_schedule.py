"""``mail.activity.schedule`` — el planificador de actividades filtrado por
departamento (Odoo ``hr``).

Adaptación de Odoo hr/wizard/mail_activity_schedule.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 54 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03).

Porte PARCIAL DECLARADO — 1 de 6 símbolos; los otros 5 BLOQUEADOS
==================================================================

La referencia extiende ``_inherit = 'mail.activity.schedule'`` (el wizard
de programar actividades/planes de ``mail``). Medido en este pase:
``grep -rln "mail.activity.schedule\\|MailActivitySchedule" addons/ src/``
→ **0 hits** — ni el wizard ni su dependencia ``mail.activity.plan``
existen (esta última medida en ``models/mail_activity_plan.py`` de este
mismo pase).

===========================================================  ================
Símbolo de la referencia (línea)                             Estado
===========================================================  ================
``department_id`` (compute, ``:12``)                         bloqueado —
                                                             campo del
                                                             wizard ausente
``plan_department_filterable`` (compute, ``:13``)            bloqueado
``_compute_plan_available_ids`` (``:15-25``)                 bloqueado —
                                                             filtra
                                                             ``mail.activity.plan``,
                                                             ausente
``_compute_plan_department_filterable`` (``:27-30``)         bloqueado —
                                                             lee
                                                             ``res_model``
                                                             del wizard
                                                             ausente
``_compute_department_id`` (``:32-40``)                      bloqueado —
                                                             ídem
``_compute_plan_date`` (``:42-54``)                          **portado** —
                                                             función de
                                                             módulo: es
                                                             pura lógica
                                                             sobre
                                                             ``hr.employee``
                                                             (fechas de
                                                             alta)
===========================================================  ================

Divergencias del símbolo portado
=================================

1. **``self._get_applied_on_records()`` → argumento ``employees``** — la
   resolución del ``res_model``/``res_ids`` del wizard es del modelo
   ausente.
2. **``relativedelta(days=+30)`` → ``timedelta(days=30)``** — mismo salto
   fijo; sin dependencia de ``dateutil``.
3. **La rama ``super()`` devuelve ``None``** — el relevo hacia el wizard
   base ausente (mismo criterio que ``_determine_responsible`` en
   ``models/mail_activity_plan_template.py``).

Sucesor: el porte de ``mail.activity.schedule`` (y de los planes de los que
depende) a ``addons/mail`` — el MISMO DESCONOCIDO con condición de cierre
que ``models/mail_activity_plan.py``.
"""
from datetime import date, timedelta


def _compute_plan_date(employees):
    """La fecha sugerida del plan de actividades — ≙ ``_compute_plan_date``
    (``odoo19c: hr/wizard/mail_activity_schedule.py:42-54``).

    La menor fecha de alta (``date_start``) de los empleados
    seleccionados; si ya pasó o está a menos de 30 días, hoy + 30 días.
    ``None`` si ningún empleado tiene fecha de alta (la rama ``super()``
    de la referencia — ver divergencia 3).
    """
    start_dates = [employee.date_start for employee in employees
                   if employee.date_start]
    if not start_dates:
        return None
    today = date.today()
    planned_due_date = min(start_dates)
    if planned_due_date < today or (planned_due_date - today).days < 30:
        return today + timedelta(days=30)
    return planned_due_date


def apply_hr_mail_activity_schedule_extensions():
    """No-op declarado — el wizard destino no existe (ver docstring)."""
    return None
