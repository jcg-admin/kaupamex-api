"""``account.analytic.line.calendar.employee`` — filtro personal de
empleados en la vista de calendario (Odoo ``hr_timesheet``).

Adaptación de Odoo ``hr_timesheet/models/
account_analytic_line_calendar_employee.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3, 12 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Porte símbolo por símbolo — 6 de la referencia
================================================

Medido por AST: 1 clase, 2 atributos de clase (``_name``, ``_description``),
4 campos. Todos portados.

======================================  ========================================
Símbolo de la referencia (línea)         Dónde queda en este puerto
======================================  ========================================
``_name`` (:6)                           ``Meta.db_table`` (verbatim,
                                          ``account_analytic_line_calendar_employee``)
``_description`` (:7)                    ``Meta.verbose_name``
``user_id`` (:9)                         ``user`` (FK ``base.ResUsers``)
``employee_id`` (:10)                    ``employee`` (FK ``hr.HrEmployee``)
``checked`` (:11)                        ``checked``
``active`` (:12)                         ``active``
======================================  ========================================

Es un modelo **propio** de este addon (no cuelga sobre uno ajeno) — la
única clase de ``hr_timesheet`` que ``models/__init__.py`` importa directo,
en vez de una función ``apply_*_extensions`` invocada desde ``ready()``.

``user`` — divergencia de mecanismo (sin default de sesión)
================================================================

``default=lambda self: self.env.user`` (:9) — sin ``env`` ambiental, el
default queda sin fijar: el campo sigue siendo ``required`` (FK no
nullable), el llamador lo declara explícito. Mismo criterio que
``AccountAnalyticLine.user`` (``api: addons/analytic/models/
analytic_line.py``, *"Sin default a env.user"*).
"""
import fields
import models

from addons.base.models import ResUsers
from addons.hr.models import HrEmployee


class AccountAnalyticLineCalendarEmployee(models.Model):
    """``account.analytic.line.calendar.employee`` — qué empleados muestra
    el calendario personal de un usuario."""

    user = fields.Many2one(
        ResUsers, on_delete=models.CASCADE, related_name='timesheet_calendar_filters',
        verbose_name='Usuario',
        help_text='Odoo user_id (required, ondelete=cascade). Sin default '
                  'a env.user — ver docstring del módulo.',
    )
    employee = fields.Many2one(
        HrEmployee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='calendar_filters', verbose_name='Empleado',
    )
    checked = fields.Boolean(default=True, verbose_name='Marcado')
    active = fields.Boolean(default=True, verbose_name='Activo')

    class Meta:
        db_table = 'account_analytic_line_calendar_employee'
        verbose_name = 'Filtro de empleado en calendario'
        verbose_name_plural = 'Filtros de empleado en calendario'

    def __str__(self):
        return f'{self.user} / {self.employee}'
