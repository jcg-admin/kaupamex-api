"""``resource.calendar.attendance`` — un tramo de horario semanal (Odoo
``resource``).

Adaptación fiel de Odoo resource/models/resource_calendar_attendance.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

Divergencias declaradas
=======================

1. **``duration_hours``/``duration_days`` NO se persisten.** En la
   referencia son ``compute='...', store=True, readonly=False`` (el usuario
   puede sobreescribirlas cuando el calendario es ``duration_based``). Aquí
   son ``@property`` calculadas en cada lectura desde ``hour_from``/
   ``hour_to``/``day_period`` — el caso ``duration_based`` (donde el usuario
   fija las horas y el sistema calcula ``hour_from``/``hour_to`` centradas en
   el mediodía) se porta como método explícito ``apply_duration_hours()``,
   invocado por el llamador (serializer) en vez de un ``inverse`` automático
   — mismo criterio que ``sync_fields_from_model()`` en ``fleet.vehicle``.
2. **``duration_based`` (``related='calendar_id.duration_based'``) es una
   ``@property``** que delega a ``self.calendar.duration_based`` — no una
   columna duplicada.
3. **``two_weeks_calendar`` (``related='calendar_id.two_weeks_calendar'``)
   idem — ``@property``.**
4. **``_onchange_hours`` (clamp de ``hour_from``/``hour_to`` a [0, 24] con
   ``hour_to >= hour_from``) NO se porta.** Es un ``@api.onchange`` de
   formulario (recalcula mientras el usuario edita, antes de guardar); sin
   vistas XML de Odoo no hay onchange que disparar — la validación
   equivalente en escritura vive en ``clean()`` (ver abajo), que rechaza en
   vez de clampear.
5. **``_compute_display_name`` (etiqueta "Primera semana (esta semana)" para
   secciones ``line_section``) NO se porta** — es texto de UI Odoo sin
   vista XML que lo consuma; ``__str__`` usa ``name`` a secas.
"""
import fields
import models
from exceptions import UserError, ValidationError

from addons.base.models import TimeStampedModel

DAYS_OF_WEEK = [
    ('0', 'Lunes'),
    ('1', 'Martes'),
    ('2', 'Miércoles'),
    ('3', 'Jueves'),
    ('4', 'Viernes'),
    ('5', 'Sábado'),
    ('6', 'Domingo'),
]

DAY_PERIODS = [
    ('morning', 'Mañana'),
    ('lunch', 'Descanso'),
    ('afternoon', 'Tarde'),
    ('full_day', 'Día completo'),
]

WEEK_TYPES = [
    ('0', 'Primera semana'),
    ('1', 'Segunda semana'),
]

DISPLAY_TYPES = [
    ('line_section', 'Sección'),
]


class ResourceCalendarAttendance(TimeStampedModel):
    """``resource.calendar.attendance`` — un tramo de trabajo de un día de
    la semana (p. ej. "Lunes mañana, 08:00-12:00")."""

    name = fields.Char(max_length=100, help_text='Odoo name.')
    dayofweek = fields.Selection(
        max_length=1, choices=DAYS_OF_WEEK, default='0',
        help_text='Odoo dayofweek (0=Lunes … 6=Domingo).',
    )
    hour_from = fields.Float(
        default=0, help_text=(
            'Hora de inicio (Odoo hour_from). Un valor de 24.0 se interpreta '
            'como 23:59:59.999999 (mismo criterio que la referencia).'
        ),
    )
    hour_to = fields.Float(default=0, help_text='Hora de fin (Odoo hour_to).')
    calendar = fields.Many2one(
        'resource.ResourceCalendar', on_delete=models.CASCADE,
        related_name='attendances',
        help_text="Odoo calendar_id (required, ondelete='cascade').",
    )
    day_period = fields.Selection(
        max_length=10, choices=DAY_PERIODS, default='morning',
        help_text='Odoo day_period.',
    )
    week_type = fields.Selection(
        max_length=1, choices=WEEK_TYPES, null=True, blank=True, default=None,
        help_text='Odoo week_type — sólo relevante si calendar.two_weeks_calendar.',
    )
    display_type = fields.Selection(
        max_length=20, choices=DISPLAY_TYPES, null=True, blank=True, default=None,
        help_text='Odoo display_type — línea técnica de sección (UI).',
    )
    sequence = fields.Integer(
        default=10, help_text='Odoo sequence — orden al listar el calendario.',
    )

    class Meta:
        db_table = 'resource_calendar_attendance'
        ordering = ['sequence', 'week_type', 'dayofweek', 'hour_from']
        verbose_name = 'Tramo de horario'
        verbose_name_plural = 'Tramos de horario'

    def __str__(self):
        return self.name or ''

    # --------------------------------------------------------------
    # Propiedades derivadas (divergencias 1-3)
    # --------------------------------------------------------------

    @property
    def duration_based(self):
        return bool(self.calendar_id and self.calendar.duration_based)

    @property
    def two_weeks_calendar(self):
        return bool(self.calendar_id and self.calendar.two_weeks_calendar)

    @property
    def duration_hours(self):
        """Horas del tramo (Odoo ``_compute_duration_hours``)."""
        if self.day_period == 'lunch':
            return 0.0
        if not self.hour_to:
            return 0.0
        return self.hour_to - self.hour_from

    @property
    def duration_days(self):
        """Días que representa el tramo (Odoo ``_compute_duration_days``)."""
        if self.day_period == 'lunch':
            return 0.0
        if self.day_period == 'full_day':
            return 1.0
        hours_per_day = self.calendar.hours_per_day if self.calendar_id else 0
        threshold = hours_per_day * 3 / 4 if hours_per_day else 0
        return 0.5 if self.duration_hours <= threshold else 1.0

    def apply_duration_hours(self, duration_hours):
        """Fija ``hour_from``/``hour_to`` desde una duración centrada según
        ``day_period`` (Odoo ``_inverse_duration_hours``, sólo aplicable
        cuando ``calendar.duration_based``). No se invoca automáticamente —
        el llamador la ejecuta explícitamente tras editar la duración."""
        if not self.duration_based:
            return
        if self.day_period == 'full_day':
            half = duration_hours / 2
            self.hour_to = 12 + half
            self.hour_from = 12 - half
        elif self.day_period == 'morning':
            self.hour_to = 12
            self.hour_from = 12 - duration_hours
        elif self.day_period == 'afternoon':
            self.hour_to = 12 + duration_hours
            self.hour_from = 12

    # --------------------------------------------------------------
    # Validación (divergencia 4)
    # --------------------------------------------------------------

    def clean(self):
        super().clean()
        if self.day_period == 'lunch' and self.duration_based:
            raise UserError(
                f'{self.name} es un tramo de descanso; no debería estar en '
                'un calendario basado en duración.'
            )
        if self.hour_from < 0 or self.hour_to > 24 or self.hour_to < self.hour_from:
            raise ValidationError(
                'hour_from/hour_to deben estar en [0, 24] con hour_to >= hour_from.'
            )

    # --------------------------------------------------------------
    # Utilidades (Odoo get_week_type / _copy_attendance_vals / _is_work_period)
    # --------------------------------------------------------------

    @staticmethod
    def get_week_type(date):
        """Paridad ISO del número de semana de ``date`` (Odoo ``get_week_type``,
        matemática pura — sin dependencia de zona horaria)."""
        return (date.toordinal() - 1) // 7 % 2

    def copy_vals(self):
        """Odoo ``_copy_attendance_vals`` — dict listo para crear un tramo
        equivalente en otro calendario."""
        return {
            'name': self.name,
            'dayofweek': self.dayofweek,
            'hour_from': self.hour_from,
            'hour_to': self.hour_to,
            'day_period': self.day_period,
            'week_type': self.week_type,
            'display_type': self.display_type,
            'sequence': self.sequence,
        }

    @property
    def is_work_period(self):
        """Odoo ``_is_work_period`` — excluye descansos y secciones técnicas."""
        return self.day_period != 'lunch' and not self.display_type
