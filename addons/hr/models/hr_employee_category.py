"""``hr.employee.category`` — etiqueta de empleado (Odoo ``hr``).

Adaptación fiel de Odoo hr/models/hr_employee_category.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

Campos fieles-mínimos: sin ``hr.employee`` (GAP grande, otro NÚCLEO — fuera
de alcance en este tramo). ``employee_ids`` queda **deferido** —ausente, no
stub— y se agrega en migración aditiva cuando ``hr.employee`` aterrice.

.. list-table:: Desenlaces de símbolos no portados verbatim
   :header-rows: 1

   * - Símbolo
     - Desenlace
     - Detalle
   * - ``employee_ids`` (``Many2many`` a ``hr.employee``)
     - BLOQUEADO
     - Requiere ``hr.employee``, explícitamente fuera de alcance de este
       tramo (``hr_employee.py`` — ver ``.. meta::`` de este hallazgo).
       Sucesor: el porte de ``hr_employee.py`` en el tramo siguiente.
   * - ``_get_default_color`` (método de instancia)
     - DIVERGENCIA de mecanismo
     - Django ``Field.default`` sólo acepta callables de cero argumentos;
       el método de la fuente recibe ``self`` sin usarlo. Se porta como
       función de módulo, mismo comportamiento (``randint(1, 11)``).
"""
from random import randint

import fields
import models

from addons.base.models import TimeStampedModel


def _default_category_color():
    """Color aleatorio del kanban — ≙ ``_get_default_color``."""
    return randint(1, 11)


class HrEmployeeCategory(TimeStampedModel):
    """``hr.employee.category`` — etiqueta libre para clasificar empleados."""

    # Atributos de clase de modelo — los dos que la referencia declara, en
    # dos asignaciones separadas (``odoo19c: hr/models/hr_employee_category.py
    # :10,12``), verbatim.
    _name = 'hr.employee.category'

    _description = "Employee Category"

    name = fields.Char(
        'Nombre de la etiqueta', max_length=150, required=True,
        help='Nombre de la etiqueta (Odoo name).',
    )
    color = fields.Integer(
        default=_default_category_color, verbose_name='Índice de color',
        help_text='Color del kanban, 1-11 (Odoo color).',
    )

    # DEFERIDO (no stub): employee_ids — requiere hr.employee (BLOQUEADO,
    # ver tabla del docstring del módulo).

    class Meta:
        db_table = 'hr_employee_category'
        verbose_name = 'Etiqueta de empleado'
        verbose_name_plural = 'Etiquetas de empleado'
        # ``_name_uniq`` de la referencia (``models.Constraint``, objeto de
        # tabla) — su hogar aquí es Meta.constraints, con el nombre
        # derivado que ``check_model_class_attributes.py`` espera:
        # f'{_table}_{attr[1:]}' → 'hr_employee_category_name_uniq'.
        constraints = [
            models.UniqueConstraint(
                fields=['name'], name='hr_employee_category_name_uniq'),
        ]

    def __str__(self):
        return self.name
