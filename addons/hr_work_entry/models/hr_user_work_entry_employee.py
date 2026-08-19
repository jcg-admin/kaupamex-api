"""``hr.user.work.entry.employee`` — filtro personal del calendario de
entradas de trabajo.

Adaptación de Odoo hr_work_entry/models/hr_user_work_entry_employee.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 20 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03).

Atributos de clase: 3/3 — ``_name``/``_description`` verbatim; el objeto de
tabla ``_user_id_employee_id_unique`` (``models.Constraint``
``UNIQUE(user_id,employee_id)``, ``:17-20``) → ``Meta.constraints`` con el
nombre de la fuente conservado (``user_id_employee_id_unique``, 26
caracteres, ≤30 — sin el guion bajo inicial, sintaxis de declaración).

Porte símbolo por símbolo — 4/4 campos, 0 métodos (la fuente no declara)
=========================================================================

- ``user_id`` → ``user`` — portado; su ``default=lambda self:
  self.env.user`` es ``get_current_uid`` (el ``env.uid`` de este árbol);
  ``ondelete='cascade'`` verbatim.
- ``employee_id`` → ``employee`` — portado.
- ``active`` / ``is_checked`` — portados.
"""
import fields
import models

from addons.base.models import ResUsers, TimeStampedModel
from orm.environments import get_current_uid


class HrUserWorkEntryEmployee(TimeStampedModel):
    """Personnal calendar filter (docstring verbatim de la fuente, ``:7``) —
    qué empleados tiene marcados cada usuario en su calendario."""

    _name = 'hr.user.work.entry.employee'
    _description = 'Work Entries Employees'

    user = fields.Many2one(
        ResUsers, on_delete=models.CASCADE, verbose_name='Me',
        related_name='work_entry_employee_filters',
        default=get_current_uid,
        help_text='Odoo user_id (required, default=env.user → '
                  'get_current_uid, ondelete=cascade).',
    )
    employee = fields.Many2one(
        'hr.HrEmployee', on_delete=models.CASCADE, verbose_name='Employee',
        related_name='work_entry_user_filters',
        help_text='Odoo employee_id (required).',
    )
    active = fields.Boolean('Active', default=True)
    is_checked = fields.Boolean(default=True)

    class Meta:
        db_table = 'hr_user_work_entry_employee'
        verbose_name = 'Filtro de empleados (entradas de trabajo)'
        verbose_name_plural = 'Filtros de empleados (entradas de trabajo)'
        constraints = [
            # ≙ ``_user_id_employee_id_unique`` (``:17-20``).
            models.UniqueConstraint(
                fields=['user', 'employee'],
                name='user_id_employee_id_unique',
                violation_error_message='You cannot have the same employee twice.',
            ),
        ]

    def __str__(self):
        return f'{self.user} → {self.employee}'
