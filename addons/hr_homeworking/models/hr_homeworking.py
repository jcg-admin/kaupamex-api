"""``hr.employee.location`` — excepción puntual de ubicación de trabajo.

Adaptación de Odoo hr_homeworking/models/hr_homeworking.py
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 28 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Es el ÚNICO modelo propio del addon: una fila = "el empleado E trabaja en la
sede S el día D", por encima de su patrón semanal (los 7 campos
``<día>_location_id`` que este mismo addon cuelga sobre ``hr.employee``).

Porte símbolo por símbolo: 10 de 10
====================================

- ``DAYS`` (``:5``): constante de módulo.
- ``_name`` / ``_description`` (``:9-10``): verbatim.
- ``work_location_id`` (``:12``): FK ``work_location_id``.
- ``work_location_name`` (``:13``): related sin columna.
- ``work_location_type`` (``:14``): related sin columna.
- ``employee_id`` (``:15``): FK con el ``default`` del usuario que actúa.
- ``employee_name`` (``:16``): related sin columna.
- ``date`` (``:17``): columna.
- ``day_week_string`` / ``_compute_day_week_string`` (``:18``,
  ``:25-28``): compute sin columna.
- ``_uniq_exceptional_per_day`` (``:20-23``): ``Meta.constraints``, con el
  nombre conservado.

Divergencias declaradas
=========================

1. **``DAYS`` con los nombres de campo de ESTE árbol** — la convención local
   pierde el sufijo ``_id`` en los relacionales (docstring de
   ``hr/models/hr_employee.py``), así que la lista es
   ``['monday_location', …]`` y no ``['monday_location_id', …]``. El nombre
   de la constante y su orden (lunes→domingo, alineado con
   ``date.weekday()``) son verbatim.
2. **``default=lambda self: self.env.user.employee_id`` → la función de
   módulo ``_default_employee``** — el serializador de migraciones rechaza
   lambdas; la función lee el usuario del entorno
   (``orm.environments.get_current_user``), que es el ``env.user`` de la
   fuente.
3. **El ``__str__`` no viene de la fuente**: es anterior a esta adopción y
   se conserva para los consumidores que lo leen.
"""

import api
import fields
import models

from addons.base.models import TimeStampedModel
from orm.environments import get_current_user
from tools.misc import format_date

#: ≙ ``DAYS`` (``odoo19c: hr_homeworking/models/hr_homeworking.py:5``) — los
#: 7 campos de ubicación semanal de ``hr.employee``, indexados por
#: ``date.weekday()`` (0=lunes). Nombres locales sin ``_id`` (divergencia 1).
DAYS = [
    'monday_location',
    'tuesday_location',
    'wednesday_location',
    'thursday_location',
    'friday_location',
    'saturday_location',
    'sunday_location',
]


def _default_employee():
    """≙ ``default=lambda self: self.env.user.employee_id`` (``:15``) — el
    empleado del usuario que actúa, o ``None`` sin usuario ni empleado."""
    user = get_current_user()
    if not user:
        return None
    return user.employee


class HrEmployeeLocation(models.BaseModel, TimeStampedModel):
    """``hr.employee.location`` — la excepción de ubicación de un día."""

    # Atributos de clase de modelo — los dos que la referencia declara
    # (``odoo19c: hr_homeworking/models/hr_homeworking.py:9-10``), verbatim.
    _name = 'hr.employee.location'
    _description = "Employee Location"

    work_location_id = fields.Many2one(
        'hr.HrWorkLocation',
        null=False, on_delete=models.PROTECT,
        related_name='homeworking_exceptions',
        verbose_name='Ubicación',
        help_text=(
            'Sede de la excepción (Odoo work_location_id, required). '
            'PROTECT: el borrado de una sede pasa por '
            '_unlink_except_used_by_employee, que limpia estas filas '
            'antes (ver hr_work_location.py de este addon).'
        ),
        db_column='work_location_id',
    )
    employee_id = fields.Many2one(
        'hr.HrEmployee',
        null=False, on_delete=models.CASCADE,
        related_name='homeworking_exceptions',
        default=_default_employee,
        verbose_name='Empleado',
        help_text=(
            'Odoo employee_id (required, ondelete=cascade; por defecto '
            'el empleado del usuario que actúa).'
        ),
        db_column='employee_id',
    )
    date = fields.Date(null=True, blank=True, verbose_name='Fecha')
    #: ≙ ``work_location_name`` (``:13``) — forma N de ADR-029.
    work_location_name = fields.Char(
        'Location name', related='work_location_id.name', store=False)
    #: ≙ ``work_location_type`` (``:14``).
    work_location_type = fields.Selection(
        related='work_location_id.location_type', store=False)
    #: ≙ ``employee_name`` (``:16``).
    employee_name = fields.Char(related='employee_id.name', store=False)
    #: ≙ ``day_week_string`` (``:18``).
    day_week_string = fields.Char(
        compute='_compute_day_week_string', store=False)

    class Meta:
        db_table = 'hr_employee_location'
        verbose_name = 'Ubicación de empleado'
        verbose_name_plural = 'Ubicaciones de empleado'
        constraints = [
            # ≙ ``_uniq_exceptional_per_day = models.Constraint('unique(
            # employee_id, date)', …)`` (``:20-23``) — nombre conservado
            # (25 caracteres, bajo el tope de 30 de models.E034).
            models.UniqueConstraint(
                fields=['employee_id', 'date'],
                name='_uniq_exceptional_per_day',
                violation_error_message=(
                    'Only one default work location and one exceptional '
                    'work location per day per employee.'
                ),
            ),
        ]

    def __str__(self):
        employee_name = self.employee_id.name if self.employee_id_id else ''
        location_name = (
            self.work_location_id.name if self.work_location_id_id else ''
        )
        return f'{employee_name} - {location_name} ({self.date})'

    @api.depends('date')
    def _compute_day_week_string(self):
        """≙ ``_compute_day_week_string`` (``:25-28``)."""
        for record in self:
            record.day_week_string = format_date(
                record.env, record.date, date_format='EEEE')
