"""``resource.calendar`` — un horario de trabajo (Odoo ``resource``).

Adaptación fiel de Odoo resource/models/resource_calendar.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 1014 líneas — el archivo más grande
del addon).

Qué SÍ se porta (fiel, sin motor de intervalos)
================================================

Todos los campos de la referencia, más la lógica que sólo depende de los
tramos semanales propios (``ResourceCalendarAttendance``) — nada de esto
requiere componer intervalos sobre un rango de fechas arbitrario:

- ``_get_default_attendance_ids``/``_get_two_weeks_attendance`` →
  ``default_attendance_specs()``/``two_weeks_attendance_specs()``.
- ``switch_calendar_type``/``switch_based_on_duration`` → igual.
- ``_check_attendance_ids``/``_check_overlap`` → ``check_attendances()``
  (validación de traslape por día de la semana, matemática pura sobre
  ``dayofweek``/``hour_from``/``hour_to`` — sin fechas).
- ``_get_days_per_week``/``_get_hours_per_week``/``_get_hours_per_day``/
  ``_get_global_attendances`` → propiedades ``hours_per_week``/
  ``hours_per_day`` (agregación sobre los tramos, no sobre un calendario).
- ``get_week_type`` → delega en ``ResourceCalendarAttendance.get_week_type``.
- ``_compute_tz_offset`` → propiedad ``tz_offset`` (usa ``zoneinfo``, ver
  divergencia 2).
- ``_compute_work_time_rate`` → propiedades ``work_time_rate``/``is_fulltime``.
- ``_compute_work_resources_count`` → propiedad ``work_resources_count``.

Qué NO se porta (DEFERIDO, no stub)
====================================

El motor de intervalos fecha/hora — ``_attendance_intervals_batch``,
``_leave_intervals_batch``, ``_work_intervals_batch``,
``_unavailable_intervals_batch``, ``_get_closest_work_time``,
``_handle_flexible_leave_interval``, ``get_work_hours_count``,
``get_work_duration_data``, ``_get_attendance_intervals_days_data``,
``plan_hours``, ``plan_days``, ``_works_on_date``, ``_get_hours_for_date``,
``_get_working_hours``, ``_get_unusual_days``, y el texto de UI
``two_weeks_explanation``.

Estos 15 métodos combinan ``dateutil.rrule``/``pytz`` con la clase propia
``Intervals`` de la referencia (fusión/resta de rangos de fecha-hora
superpuestos) para responder "¿está disponible este recurso entre estas dos
fechas?" — el problema central de agenda/planificación. **Es gap de
alcance, no incapacidad del stack:** ninguna de las dos librerías es
dependencia del proyecto, pero el motor se puede construir con ``zoneinfo``
(stdlib) + álgebra de intervalos propia el día que exista un UC de
disponibilidad/agenda que lo consuma. Hoy no existe ninguno — medido:
``mrp.workcenter``/``project.project`` (los dos puntos de la referencia que
consumen este motor vía ``resource.mixin``/campos directos) ya están
portados en ``src/addons/{mrp,project}/`` sin él (``grep -rn resource
src/addons/{mrp,project}/models/*.py`` → 0 hits). Construirlo especulativamente
violaría ``docs-design-first-rup.md`` (diseño-primero: UC → diseño →
implementación, no al revés).

Divergencias declaradas
=======================

1. **``flexible_hours`` es una ``@property`` con setter** (no
   ``compute=..., store=True, inverse=...``) — delega en/escribe
   ``schedule_type``, sin columna duplicada.
2. **``tz`` usa ``zoneinfo`` en vez de ``pytz``** (ver
   ``_timezone_choices.py``); ``tz_offset`` usa
   ``datetime.now(ZoneInfo(self.tz))`` en vez de ``pytz.timezone``.
3. **``hours_per_day``/``hours_per_week`` son propiedades**, no columnas
   ``compute=..., store=True, readonly=False`` — se recalculan en cada
   lectura desde los tramos (``self.attendances``); son baratas (una lista
   de tramos por calendario, nunca miles de filas) y evitan el riesgo de
   quedar desincronizadas tras editar un tramo sin re-guardar el calendario.
4. **``full_time_required_hours`` SÍ es una columna real** (a diferencia de
   los dos anteriores) porque la referencia la declara editable
   independientemente del cálculo (``readonly=False``) — se sincroniza con
   ``sync_full_time_required_hours()``, invocado explícitamente por el
   llamador cuando corresponda (mismo criterio que
   ``FleetVehicle.sync_fields_from_model()``), no en cada ``save()``.
5. **``is_default`` es un campo NUEVO, propio de este porte** (no existe en
   la referencia) — resuelve el problema de que Odoo modela "el calendario
   por defecto de la compañía" como una columna ``resource_calendar_id`` EN
   ``res.company``, y este addon no edita ``base/models/res_company.py`` (no
   es su dueño). Ver el docstring de ``res_company.py`` de este mismo addon
   para el patrón completo (propiedad asignada sobre la clase, análogo a
   ``sale_subscription/models/res_company.py``).
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings

import fields
import models
from exceptions import ValidationError

from addons.base.models import ResCompany, TimeStampedModel

from ._timezone_choices import TZ_CHOICES, TZ_MAX_LENGTH
from .resource_calendar_attendance import ResourceCalendarAttendance

SCHEDULE_TYPES = [
    ('flexible', 'Flexible'),
    ('fully_fixed', 'Totalmente fijo'),
]

_DEFAULT_WEEK_SPEC = [
    ('Lunes', '0'), ('Martes', '1'), ('Miércoles', '2'),
    ('Jueves', '3'), ('Viernes', '4'),
]


class ResourceCalendar(TimeStampedModel):
    """``resource.calendar`` — horario de trabajo asociado a recursos."""

    name = fields.Char(max_length=200, help_text='Odoo name (required).')
    active = fields.Boolean(
        default=True,
        help_text=(
            'Odoo active — archivar el horario sin borrarlo ni afectar a '
            'los recursos que lo usan.'
        ),
    )
    company = fields.Many2one(
        ResCompany, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resource_calendars', help_text='Odoo company_id.',
    )
    schedule_type = fields.Selection(
        max_length=12, choices=SCHEDULE_TYPES, default='fully_fixed',
        help_text='Odoo schedule_type (required).',
    )
    duration_based = fields.Boolean(
        default=False,
        help_text=(
            'Odoo duration_based — las horas se centran en las 12:00 para '
            'cubrir la duración del día, en vez de horas fijas de inicio/fin.'
        ),
    )
    full_time_required_hours = fields.Float(
        default=0,
        help_text=(
            'Odoo full_time_required_hours (compute+store, readonly=False '
            'en la referencia) — sincronizar con '
            'sync_full_time_required_hours() (divergencia 4).'
        ),
    )
    two_weeks_calendar = fields.Boolean(
        default=False, help_text='Odoo two_weeks_calendar.',
    )
    tz = fields.Selection(
        max_length=TZ_MAX_LENGTH, choices=TZ_CHOICES,
        default=settings.TIME_ZONE,
        help_text='Odoo tz (required) — zona horaria en la que trabajan los recursos.',
    )
    is_default = fields.Boolean(
        default=False,
        help_text=(
            'NUEVO (no existe en la referencia) — marca el calendario por '
            'defecto de la compañía (Odoo res.company.resource_calendar_id, '
            'columna que este addon no puede declarar — ver divergencia 5).'
        ),
    )

    class Meta:
        db_table = 'resource_calendar'
        ordering = ['company', 'name']
        verbose_name = 'Calendario de trabajo'
        verbose_name_plural = 'Calendarios de trabajo'

    def __str__(self):
        return self.name

    # --------------------------------------------------------------
    # flexible_hours (divergencia 1)
    # --------------------------------------------------------------

    @property
    def flexible_hours(self):
        return self.schedule_type == 'flexible'

    @flexible_hours.setter
    def flexible_hours(self, value):
        self.schedule_type = 'flexible' if value else 'fully_fixed'

    # --------------------------------------------------------------
    # tz_offset (divergencia 2)
    # --------------------------------------------------------------

    @property
    def tz_offset(self):
        tzinfo = ZoneInfo(self.tz or 'UTC')
        return datetime.now(tzinfo).strftime('%z')

    # --------------------------------------------------------------
    # Agregación sobre tramos — sin motor de intervalos (divergencia 3)
    # --------------------------------------------------------------

    def _global_attendances(self):
        """Odoo ``_get_global_attendances`` — tramos reales de trabajo
        (excluye descansos y secciones técnicas)."""
        return [a for a in self.attendances.all() if a.is_work_period]

    def _days_per_week(self):
        """Odoo ``_get_days_per_week``."""
        attendances = self._global_attendances()
        if self.two_weeks_calendar:
            week0 = {a.dayofweek for a in attendances if a.week_type == '0'}
            week1 = {a.dayofweek for a in attendances if a.week_type == '1'}
            return (len(week0) + len(week1)) / 2
        return len({a.dayofweek for a in attendances})

    @property
    def hours_per_week(self):
        """Odoo ``_get_hours_per_week`` — expuesta como propiedad (divergencia 3)."""
        if self.flexible_hours:
            return 0.0
        total = 0.0
        for attendance in self._global_attendances():
            total += (
                attendance.duration_hours if self.duration_based
                else attendance.hour_to - attendance.hour_from
            )
        return total / 2 if self.two_weeks_calendar else total

    @property
    def hours_per_day(self):
        """Odoo ``_get_hours_per_day``."""
        if self.flexible_hours:
            return 0.0
        days = self._days_per_week()
        return self.hours_per_week / days if days else 0.0

    @property
    def is_fulltime(self):
        return abs(self.full_time_required_hours - self.hours_per_week) < 1e-3

    @property
    def work_time_rate(self):
        if not self.full_time_required_hours:
            return 100.0
        return self.hours_per_week / self.full_time_required_hours * 100

    @property
    def work_resources_count(self):
        return self.resources.count()

    def sync_full_time_required_hours(self):
        """Sincroniza ``full_time_required_hours`` desde el calendario por
        defecto de la compañía (Odoo ``_compute_full_time_required_hours``,
        invocación explícita — divergencia 4)."""
        if not self.company_id:
            return
        default_calendar = self.company.resource_calendar
        if default_calendar is not None and default_calendar.pk != self.pk:
            self.full_time_required_hours = default_calendar.hours_per_week

    # --------------------------------------------------------------
    # Validación (Odoo _check_attendance_ids / _check_overlap)
    # --------------------------------------------------------------

    def check_attendances(self):
        """Odoo ``_check_attendance_ids``/``_check_overlap`` — sin traslapes
        dentro de un mismo día de la semana (y, en calendario de dos
        semanas, dentro de la misma semana)."""
        real_attendances = [
            a for a in self.attendances.all() if not a.display_type
        ]
        if self.two_weeks_calendar:
            self._check_overlap([a for a in real_attendances if a.week_type == '0'])
            self._check_overlap([a for a in real_attendances if a.week_type == '1'])
        else:
            self._check_overlap(real_attendances)

    @staticmethod
    def _check_overlap(attendances):
        intervals = sorted(
            (
                int(a.dayofweek) * 24 + a.hour_from + 0.000001,
                int(a.dayofweek) * 24 + a.hour_to,
            )
            for a in attendances
        )
        previous_end = None
        for start, end in intervals:
            if previous_end is not None and start < previous_end:
                raise ValidationError('Los tramos de horario no pueden traslaparse.')
            previous_end = end if previous_end is None else max(previous_end, end)

    # --------------------------------------------------------------
    # Generación de tramos por defecto (Odoo _get_default_attendance_ids /
    # _get_two_weeks_attendance)
    # --------------------------------------------------------------

    @classmethod
    def default_attendance_specs(cls, template_company=None):
        """Odoo ``_get_default_attendance_ids`` — lista de specs (dicts) para
        crear los tramos por defecto: copia del calendario por defecto de
        ``template_company`` si tiene uno con tramos, o el estándar de
        40 horas/semana."""
        if template_company is not None:
            default_calendar = template_company.resource_calendar
            if default_calendar is not None:
                attendances = list(default_calendar.attendances.all())
                if attendances:
                    return [a.copy_vals() for a in attendances]
        specs = []
        for day_name, day_code in _DEFAULT_WEEK_SPEC:
            specs.append({
                'name': f'{day_name} mañana', 'dayofweek': day_code,
                'hour_from': 8, 'hour_to': 12, 'day_period': 'morning',
            })
            specs.append({
                'name': f'{day_name} descanso', 'dayofweek': day_code,
                'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch',
            })
            specs.append({
                'name': f'{day_name} tarde', 'dayofweek': day_code,
                'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon',
            })
        return specs

    def create_default_attendances(self, template_company=None):
        """Crea los tramos por defecto para este calendario (ver
        ``default_attendance_specs``)."""
        specs = self.default_attendance_specs(template_company=template_company)
        ResourceCalendarAttendance.objects.bulk_create([
            ResourceCalendarAttendance(calendar=self, **spec) for spec in specs
        ])

    def two_weeks_attendance_specs(self):
        """Odoo ``_get_two_weeks_attendance`` — duplica los tramos actuales
        en semana 0 y semana 1, con dos secciones técnicas iniciales."""
        specs = [
            {
                'name': 'Primera semana', 'dayofweek': '0', 'sequence': 0,
                'hour_from': 0, 'hour_to': 0, 'day_period': 'morning',
                'week_type': '0', 'display_type': 'line_section',
            },
            {
                'name': 'Segunda semana', 'dayofweek': '0', 'sequence': 25,
                'hour_from': 0, 'hour_to': 0, 'day_period': 'morning',
                'week_type': '1', 'display_type': 'line_section',
            },
        ]
        for index, attendance in enumerate(self.attendances.all()):
            for week_type, offset in (('0', 1), ('1', 26)):
                vals = attendance.copy_vals()
                vals['week_type'] = week_type
                vals['sequence'] = index + offset
                specs.append(vals)
        return specs

    def switch_calendar_type(self):
        """Odoo ``switch_calendar_type``."""
        if not self.two_weeks_calendar:
            self.two_weeks_calendar = True
            specs = self.two_weeks_attendance_specs()
            self.attendances.all().delete()
            ResourceCalendarAttendance.objects.bulk_create([
                ResourceCalendarAttendance(calendar=self, **spec) for spec in specs
            ])
        else:
            self.two_weeks_calendar = False
            self.attendances.all().delete()
            self.duration_based = False
            self.create_default_attendances()
        self.save()

    def switch_based_on_duration(self):
        """Odoo ``switch_based_on_duration``."""
        self.duration_based = not self.duration_based
        if self.duration_based:
            self.attendances.filter(day_period='lunch').delete()
        else:
            self.attendances.all().delete()
            self.create_default_attendances()
            if self.two_weeks_calendar:
                specs = self.two_weeks_attendance_specs()
                self.attendances.all().delete()
                ResourceCalendarAttendance.objects.bulk_create([
                    ResourceCalendarAttendance(calendar=self, **spec) for spec in specs
                ])
        self.save()
