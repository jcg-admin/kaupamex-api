"""``resource.resource`` — un recurso planificable: persona o material (Odoo
``resource``).

Adaptación fiel de Odoo resource/models/resource_resource.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

Divergencias declaradas
=======================

1. **``avatar_128``/``share``/``email``/``phone`` son ``@property`` que
   delegan a ``self.user``**, no columnas ``related=`` duplicadas — mismo
   criterio que los passthroughs de imagen en ``fleet.vehicle``.
2. **``tz`` usa ``zoneinfo`` en vez de ``pytz``** — ver
   ``_timezone_choices.py``.
3. **DEFERIDO (no stub) — el motor de intervalos fecha/hora.** La
   referencia calcula disponibilidad real (``_adjust_to_calendar``,
   ``_get_unavailable_intervals``, ``_get_valid_work_intervals``,
   ``_get_flexible_resources_default_work_intervals``,
   ``_get_flexible_resources_calendars_validity_within_period``,
   ``_format_leave``, ``_get_flexible_resource_valid_work_intervals``,
   ``_get_flexible_resource_work_hours``) componiendo intervalos de fecha/hora
   con ``dateutil.rrule``/``pytz`` y su propia clase ``Intervals`` (fusión de
   rangos superpuestos). Ninguna de las dos librerías es dependencia del
   proyecto, y **hoy no hay ningún consumidor**: ``mrp.workcenter`` y
   ``project.project`` (los dos `_inherit`/campo que en la referencia usan
   ``resource``) ya están portados en ``src/addons/{mrp,project}/`` **sin**
   tocar ``resource`` — medido con ``grep -rn resource src/addons/{mrp,
   project}/models/*.py`` → 0 hits (ver ``analisis-familia-resource``, sección
   "Consumidores medidos"). Es **gap de alcance**, no incapacidad del stack:
   el motor se puede construir con ``zoneinfo`` + álgebra de intervalos propia
   (sin ``Intervals`` de terceros) el día que un UC de agenda/disponibilidad
   lo necesite (diseño-primero, ``docs-design-first-rup.md``) — construirlo
   especulativamente sin ese UC repetiría el patrón que esa regla prohíbe.
   Lo que SÍ se porta son los predicados que NO requieren el motor:
   ``is_fully_flexible``/``is_flexible`` (leen sólo ``calendar.flexible_hours``,
   sin fecha de por medio) y ``calendar_at()`` (hoy trivialmente
   ``self.calendar``, sin historial de calendarios por período — la
   referencia ya lo simplifica igual en su base, dejando el caso multi-periodo
   a módulos de RRHH que tampoco están portados).
"""
import fields
import models

from addons.base.models import ResCompany, ResUsers, TimeStampedModel

from ._timezone_choices import TZ_CHOICES, TZ_MAX_LENGTH

RESOURCE_TYPES = [
    ('user', 'Humano'),
    ('material', 'Material'),
]


class ResourceResource(TimeStampedModel):
    """``resource.resource`` — algo planificable: una persona o una
    máquina/centro de trabajo."""

    name = fields.Char(max_length=200, help_text='Odoo name.')
    active = fields.Boolean(
        default=True,
        help_text='Odoo active — archivar sin borrar (Odoo active).',
    )
    company = fields.Many2one(
        ResCompany, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resource_resources', help_text='Odoo company_id.',
    )
    resource_type = fields.Selection(
        max_length=10, choices=RESOURCE_TYPES, default='user',
        help_text='Odoo resource_type.',
    )
    user = fields.Many2one(
        ResUsers, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resource_resources',
        help_text='Odoo user_id — usuario relacionado, para gestionar accesos.',
    )
    time_efficiency = fields.Float(
        default=100, help_text=(
            'Odoo time_efficiency — factor de eficiencia %; 200% implica la '
            'mitad del tiempo esperado.'
        ),
    )
    calendar = fields.Many2one(
        'resource.ResourceCalendar', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resources',
        help_text=(
            'Odoo calendar_id — horario de trabajo. Vacío = horario '
            'completamente flexible.'
        ),
    )
    tz = fields.Selection(
        max_length=TZ_MAX_LENGTH, choices=TZ_CHOICES,
        help_text='Odoo tz — zona horaria del recurso.',
    )

    class Meta:
        db_table = 'resource_resource'
        ordering = ['name']
        verbose_name = 'Recurso'
        verbose_name_plural = 'Recursos'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(time_efficiency__gt=0),
                name='resource_resource_time_efficiency_positive',
            ),
        ]

    def __str__(self):
        return self.name or ''

    # --------------------------------------------------------------
    # Passthroughs al usuario (divergencia 1)
    # --------------------------------------------------------------

    @property
    def avatar_128(self):
        return self.user.avatar_128 if self.user_id else None

    @property
    def share(self):
        return bool(self.user_id and self.user.share)

    @property
    def email(self):
        return self.user.email if self.user_id else ''

    @property
    def phone(self):
        return self.user.phone if self.user_id else ''

    # --------------------------------------------------------------
    # Defaults al guardar (Odoo default_get + create)
    # --------------------------------------------------------------

    def save(self, *args, **kwargs):
        if self.company_id and not self.calendar_id:
            self.calendar = self.company.resource_calendar
        if not self.tz:
            # La precedencia usuario > calendario es de la referencia, y
            # **ya está activa**: ``res.users`` delega en ``res.partner`` por
            # el mecanismo ``_inherits`` (``orm/inherits.py``), así que
            # ``self.user.tz`` resuelve al partner igual que en la referencia
            # (``odoo19c: odoo/addons/base/models/res_users.py:165``).
            #
            # Estuvo inerte mientras la delegación no existía —el campo vivía
            # en el partner pero el usuario no lo exponía— y esa rama lanzaba
            # ``AttributeError``. Ver H-API-300. El ``getattr`` se conserva
            # como cinturón: un usuario sin partner no debe reventar aquí.
            user_tz = getattr(self.user, 'tz', None) if self.user_id else None
            if user_tz:
                self.tz = user_tz
            elif self.calendar_id and self.calendar.tz:
                self.tz = self.calendar.tz
        super().save(*args, **kwargs)

    # --------------------------------------------------------------
    # Predicados sin motor de intervalos (divergencia 3)
    # --------------------------------------------------------------

    @property
    def is_fully_flexible(self):
        """Odoo ``_is_fully_flexible`` — sin calendario asignado."""
        return not self.calendar_id

    @property
    def is_flexible(self):
        """Odoo ``_is_flexible`` — sin calendario, o calendario flexible."""
        return self.is_fully_flexible or (self.calendar_id and self.calendar.flexible_hours)

    def calendar_at(self, date_target=None, tz=None):
        """Odoo ``_get_calendar_at`` — el calendario vigente en una fecha.

        La referencia ya deja el caso base como ``self.calendar_id`` (sin
        historial de calendarios por período; eso lo agregarían módulos de
        RRHH no portados). ``date_target``/``tz`` se aceptan por paridad de
        firma pero no afectan el resultado hoy.
        """
        return self.calendar
