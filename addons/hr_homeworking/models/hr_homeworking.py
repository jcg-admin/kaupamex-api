"""``hr.employee.location`` — excepción puntual de ubicación de trabajo.

Adaptación de Odoo hr_homeworking/models/hr_homeworking.py
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 28 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Es el ÚNICO modelo propio del addon: una fila = "el empleado E trabaja en la
sede S el día D", por encima de su patrón semanal (los 7 campos
``<día>_location_id`` que este mismo addon cuelga sobre ``hr.employee``).

Porte símbolo por símbolo — 10 símbolos de la referencia
==========================================================

===========================================================  ==================
Símbolo de la referencia (línea)                             Dónde queda aquí
===========================================================  ==================
``DAYS`` (``:5``)                                            constante módulo
``_name`` / ``_description`` (``:9-10``)                     verbatim
``work_location_id`` (``:12``)                               FK ``work_location``
``work_location_name`` (``:13``, related)                    property
``work_location_type`` (``:14``, related)                    property
``employee_id`` (``:15``)                                    FK ``employee``
``employee_name`` (``:16``, related)                         property
``date`` (``:17``)                                           columna
``day_week_string`` / ``_compute_day_week_string``           property (nombre
(``:18``, ``:26-28``)                                        verbatim del
                                                             compute)
``_uniq_exceptional_per_day`` (``:20-23``)                   ``Meta.constraints``
                                                             (nombre conservado)
===========================================================  ==================

Divergencias declaradas
=========================

1. **``DAYS`` con los nombres de campo de ESTE árbol** — la convención local
   pierde el sufijo ``_id`` en los relacionales (docstring de
   ``hr/models/hr_employee.py``), así que la lista es
   ``['monday_location', …]`` y no ``['monday_location_id', …]``. El nombre
   de la constante y su orden (lunes→domingo, alineado con
   ``date.weekday()``) son verbatim.
2. **``default=lambda self: self.env.user.employee_id`` NO se porta** — dos
   razones medidas: el serializador de migraciones rechaza lambdas (regla 3
   de la tanda) y no hay usuario ambiente en la capa de modelo (mismo
   criterio que ``hr/wizard/hr_departure_wizard.py``: el llamador pasa el
   empleado explícito).
3. **``tools.format_date(env, date, date_format='EEEE')`` →
   ``django.utils.formats.date_format(date, 'l')``** — medido: no existe
   ``format_date`` en ``src/tools`` (``grep -rn "def format_date"
   src/tools/*.py`` → 0). ``'l'`` es el nombre completo del día localizado,
   el mismo significado que el patrón ``EEEE`` de babel.
4. **Los ``related`` no almacenados son properties** — mismo criterio que
   todo el árbol (``fleet_vehicle_log_contract.purchaser``).
"""
import fields
import models
from django.utils import formats

from addons.base.models import TimeStampedModel

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


class HrEmployeeLocation(TimeStampedModel):
    """``hr.employee.location`` — la excepción de ubicación de un día."""

    # Atributos de clase de modelo — los dos que la referencia declara
    # (``odoo19c: hr_homeworking/models/hr_homeworking.py:9-10``), verbatim.
    _name = 'hr.employee.location'
    _description = "Employee Location"

    work_location_id = fields.Many2one(
        'hr.HrWorkLocation', on_delete=models.PROTECT,
        related_name='homeworking_exceptions',
        verbose_name='Ubicación',
        help_text='Sede de la excepción (Odoo work_location_id, required). '
                  'PROTECT: el borrado de una sede pasa por '
                  '_unlink_except_used_by_employee, que limpia estas filas '
                  'antes (ver hr_work_location.py de este addon).',
        db_column='work_location_id',
    )
    employee_id = fields.Many2one(
        'hr.HrEmployee', on_delete=models.CASCADE,
        related_name='homeworking_exceptions',
        verbose_name='Empleado',
        help_text='Odoo employee_id (required, ondelete=cascade; su default '
                  'de usuario ambiente no se porta — divergencia 2).',
        db_column='employee_id',
    )
    date = fields.Date(null=True, blank=True, verbose_name='Fecha')

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
        location_name = self.work_location_id.name if self.work_location_id_id else ''
        return f'{employee_name} - {location_name} ({self.date})'

    # --- related no almacenados → properties (divergencia 4) ---------------

    @property
    def work_location_name(self):
        """≙ ``work_location_name`` (``related='work_location_id.name'``)."""
        return self.work_location_id.name if self.work_location_id_id else ''

    @property
    def work_location_type(self):
        """≙ ``work_location_type`` (``related='work_location_id.location_type'``)."""
        return self.work_location_id.location_type if self.work_location_id_id else ''

    @property
    def employee_name(self):
        """≙ ``employee_name`` (``related='employee_id.name'``)."""
        return self.employee_id.name if self.employee_id_id else ''

    @property
    def day_week_string(self):
        """≙ ``day_week_string`` / ``_compute_day_week_string`` (``:26-28``)
        — el nombre del día de la semana de ``date``, localizado
        (divergencia 3: ``'l'`` de Django en vez de ``EEEE`` de babel)."""
        if not self.date:
            return ''
        return formats.date_format(self.date, 'l')
