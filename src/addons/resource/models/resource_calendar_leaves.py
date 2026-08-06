"""``resource.calendar.leaves`` — una ausencia/tiempo libre (Odoo ``resource``).

Adaptación fiel de Odoo resource/models/resource_calendar_leaves.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

Divergencias declaradas
=======================

1. **``company``/``calendar`` son columnas reales sincronizadas en
   ``save()``**, no ``compute=..., store=True`` — el efecto observable es
   idéntico (ambas quedan pobladas y consultables), pero la sincronización
   ocurre en ``save()`` en vez de en un grafo de dependencias ``@api.depends``.
2. **El default de ``date_from``/``date_to`` (día completo de hoy, en la
   zona horaria del calendario) usa ``zoneinfo`` de la librería estándar, no
   ``pytz``** — ninguno de los dos es dependencia del proyecto; ``zoneinfo``
   ya está en la stdlib desde Python 3.9 (el proyecto declara
   ``>=3.12,<3.15``), así que no se agrega ninguna dependencia nueva.
3. **Los datetimes quedan timezone-aware (UTC), NO naive.** La referencia
   guarda naive-UTC porque su ORM lo asume; este proyecto declara
   ``USE_TZ = True`` (``config/settings/base.py:269``), así que Django
   **espera** datetimes aware. Es la MISMA decisión ya tomada y documentada
   en ``certificate/models/certificate.py`` (divergencia 2), y por la misma
   razón medida: un ``.replace(tzinfo=None)`` aquí produce
   ``RuntimeWarning: received a naive datetime while time zone support is
   active`` y comparaciones incorrectas contra ``timezone.now()``.

   El porte original de este archivo hacía el ``replace`` —copiando la
   convención de la referencia en vez de la decisión ya vigente del árbol— y
   la suite lo delató con ese warning exacto. Corregido para que las dos
   familias de la misma ola no sostengan convenciones opuestas sobre el
   mismo ``USE_TZ``.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone as django_tz

import fields
import models
from exceptions import ValidationError

from addons.base.models import TimeStampedModel

TIME_TYPES = [
    ('leave', 'Ausencia'),
    ('other', 'Otro'),
]


class ResourceCalendarLeaves(TimeStampedModel):
    """``resource.calendar.leaves`` — una ausencia general de la compañía o
    de un recurso concreto."""

    name = fields.Char(max_length=200, blank=True, default='', help_text='Odoo name.')
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resource_leaves',
        help_text='Odoo company_id (compute+store; aquí sincronizado en save()).',
    )
    calendar = fields.Many2one(
        'resource.ResourceCalendar', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='leaves',
        help_text='Odoo calendar_id (compute+store, readonly=False).',
    )
    date_from = fields.Datetime(help_text='Odoo date_from (required).')
    date_to = fields.Datetime(
        null=True, blank=True,
        help_text='Odoo date_to (compute+store, readonly=False).',
    )
    resource = fields.Many2one(
        'resource.ResourceResource', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='leaves',
        help_text=(
            'Odoo resource_id. Vacío = ausencia general de la compañía; '
            'con valor = ausencia sólo de ese recurso.'
        ),
    )
    time_type = fields.Selection(
        max_length=10, choices=TIME_TYPES, default='leave',
        help_text='Odoo time_type (leave vs formación/otro).',
    )

    class Meta:
        db_table = 'resource_calendar_leaves'
        ordering = ['date_from']
        verbose_name = 'Ausencia de calendario'
        verbose_name_plural = 'Ausencias de calendario'

    def __str__(self):
        return self.name or f'{self.date_from} — {self.date_to}'

    def save(self, *args, **kwargs):
        # Odoo `_compute_calendar_id`: si hay recurso, el calendario sigue al
        # del recurso.
        if self.resource_id and not self.calendar_id:
            self.calendar = self.resource.calendar
        # Odoo `_compute_company_id`: la compañía sigue al calendario.
        if self.calendar_id and not self.company_id:
            self.company = self.calendar.company
        # Odoo `default_get`: día completo de hoy si no se dio ningún rango.
        if self.date_from is None and self.date_to is None:
            self._set_default_full_day()
        # Odoo `_compute_date_to`: si sólo se dio date_from, cierra el día.
        elif self.date_from and (self.date_to is None or self.date_to <= self.date_from):
            self._close_day_from_date_from()
        super().save(*args, **kwargs)

    def _set_default_full_day(self):
        tz_name = (self.calendar.tz if self.calendar_id else None) or settings.TIME_ZONE
        tzinfo = ZoneInfo(tz_name)
        today = django_tz.localdate()
        local_start = datetime.combine(today, time.min, tzinfo=tzinfo)
        local_end = datetime.combine(today, time.max, tzinfo=tzinfo)
        self.date_from = local_start.astimezone(ZoneInfo('UTC'))
        self.date_to = local_end.astimezone(ZoneInfo('UTC'))

    def _close_day_from_date_from(self):
        tz_name = (self.calendar.tz if self.calendar_id else None) or settings.TIME_ZONE
        tzinfo = ZoneInfo(tz_name)
        local_from = django_tz.localtime(self.date_from, tzinfo)
        local_end = datetime.combine(local_from.date(), time(23, 59, 59), tzinfo=tzinfo)
        self.date_to = local_end.astimezone(ZoneInfo('UTC'))

    def clean(self):
        super().clean()
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValidationError(
                'La fecha de inicio de la ausencia debe ser anterior a la de fin.'
            )

    def copy_vals(self):
        """Odoo ``_copy_leave_vals`` — dict para replicar la ausencia en otro
        calendario (p. ej. al copiar un calendario company-wide)."""
        return {
            'name': self.name,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'time_type': self.time_type,
        }
