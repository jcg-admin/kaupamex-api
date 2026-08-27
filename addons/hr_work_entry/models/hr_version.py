"""Extensión de ``hr.version`` — generación de entradas de trabajo.

Adaptación de Odoo hr_work_entry/models/hr_version.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 729 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03).

``_inherit`` no es un símbolo a portar: lo expresa ``extend_model`` (criterio
de ``hr/models/resource_calendar.py``); el destino es el par de Django
(``'hr', 'HrVersion'``).

Porte símbolo por símbolo — 5 campos + 33 métodos (medidos por AST)
====================================================================

Campos (5):

- **Columna (4)** vía ``campos=``: ``date_generated_from`` (``:20-22``),
  ``date_generated_to`` (``:23-25``), ``last_generation_date`` (``:26``),
  ``work_entry_source`` (``:27-33``). Los ``groups=``/``tracking=`` de la
  fuente son ACL/chatter del cliente Odoo — no se portan (D-1).
- **Property (1)** vía ``propiedades=``: ``work_entry_source_calendar_invalid``
  (``:34-37``, compute sin store) con ``_compute_work_entry_source_calendar_
  invalid`` (``:39-42``) como getter.

Métodos (33): **20 portados** · **1 realizado como property** (el compute de
arriba) · **12 BLOQUEADOS** con su pieza nombrada.

Portados (20): ``_get_default_work_entry_type_id`` (``:44-47``),
``_get_default_work_entry_type_overtime_id`` (``:49-52``),
``_get_leave_work_entry_type_dates`` (``:54-55``),
``_get_leave_work_entry_type`` (``:57-58``),
``_get_more_vals_attendance_interval`` (``:61-62``),
``_get_more_vals_leave_interval`` (``:64-66``),
``_get_bypassing_work_entry_type_codes`` (``:68-69``),
``_get_interval_leave_work_entry_type`` (``:71-82``),
``_get_sub_leave_domain`` (``:84-85``), ``_get_leave_domain`` (``:87-94``),
``_get_resource_calendar_leaves`` (``:96-97``),
``_get_interval_work_entry_type`` (``:139-143``),
``_get_valid_leave_intervals`` (``:145-147``),
``_get_whitelist_fields_from_template`` (``:149-151``, encadenado con
``combine=extend_list`` — el ``super() + ['work_entry_source']``),
``_get_real_attendance_work_entry_vals`` (``:153-170``),
``has_static_work_entries`` (``:388-392``),
``_generate_work_entries_postprocess_adapt_to_calendar`` (``:499-503``),
``_remove_work_entries`` (``:626-644``), ``_cancel_work_entries``
(``:646-663``), ``_get_fields_that_recompute_we`` (``:694-696``).

BLOQUEADOS (12) — cada uno con la pieza que falta, greppeable:

- ``_get_attendance_intervals`` (``:99-119``), ``_get_lunch_intervals``
  (``:121-137``), ``_get_version_work_entries_values`` (``:172-339``),
  ``_get_real_attendances`` (``:341-343``), ``_get_work_entries_values``
  (``:345-386``), ``generate_work_entries`` (``:394-418``),
  ``_generate_work_entries`` (``:420-497``) — **Bloqueado por motor de
  intervalos** (``resource: models/resource_calendar.py``, sección "Qué NO
  se porta": ``Intervals`` + ``_attendance_intervals_batch`` DEFERIDOS).
  Condición de cierre: la misma de aquel DEFERIDO — un UC de
  disponibilidad/agenda que financie el motor (``zoneinfo`` + álgebra de
  intervalos propia); al existir, estos 7 se portan encima.
- ``_generate_work_entries_postprocess`` (``:505-624``) — **Bloqueado por
  ``_get_work_days_data_batch``** (ausente en ``hr.employee`` de este árbol —
  medido: ``grep -n _get_work_days_data_batch addons/hr/models/
  hr_employee.py`` → 0 hits) y por ser consumidor exclusivo de los 7 de
  arriba.
- ``_recompute_work_entries`` (``:684-692``) — **Bloqueado por
  ``HrWorkEntryRegenerationWizard.regenerate_work_entries``** (a su vez
  bloqueado por ``generate_work_entries``; ver ``wizard/``).
- ``write`` (``:665-678``) / ``unlink`` (``:680-682``) — **Bloqueado por la
  familia (c) de ``hr/models/hr_version.py``** (``write(vals)`` con
  inspección de claves cambiadas + disparo de recómputo, sin equivalente en
  ``save()``); su efecto útil aquí (``_remove_work_entries`` /
  ``_cancel_work_entries``) SÍ está portado como métodos explícitos que la
  capa de servicio invoca al mover fechas de contrato o borrar la versión.
- ``_cron_generate_missing_work_entries`` (``:698-729``) — **Bloqueado por
  ``generate_work_entries``** (misma cadena del motor); al desbloquear,
  su ``relativedelta`` se sustituye por aritmética de calendario
  (``base_automation.advance_date`` — dateutil NO es dependencia, medido
  ``grep -i dateutil uv.lock`` → 0).

Divergencias declaradas
========================

1. **``groups=``/``tracking=``** de los campos — ACL de grupos y chatter del
   cliente Odoo; sin equivalente aquí (la autorización es por capacidad en
   la capa DRF).
2. **``@ormcache`` → consulta directa** en los dos
   ``_get_default_work_entry_type*`` — sin el caché del registry de Odoo; el
   costo es un ``SELECT`` por llamada sobre un catálogo de decenas de filas.
3. **``env.ref(XML id)`` → ``code``** — los XML ids de ``data/`` no se
   cargan; ``work_entry_type_attendance``→``WORK100``,
   ``work_entry_type_overtime``→``OVERTIME``,
   ``work_entry_type_leave``→``LEAVE100`` (``odoo19c:
   hr_work_entry/data/hr_work_entry_type_data.xml:3-33``).
4. **``Domain`` → ``models.Q``/queryset** en ``_get_sub_leave_domain`` /
   ``_get_leave_domain`` / ``_get_resource_calendar_leaves``; los extremos
   de fecha se pasan tal cual al ORM (USE_TZ=True: aware).
5. **Recordset → instancia** — los métodos operan sobre UNA versión (mismo
   criterio que el resto del árbol); los agrupados por lote de la fuente
   viven en los métodos bloqueados del motor.
6. **``pytz`` → ``datetime.timezone``/``zoneinfo``** (pytz NO es dependencia,
   medido ``grep -i pytz uv.lock`` → 0) — misma decisión que
   ``resource/models/resource_calendar_leaves.py``.
7. **``queryset.delete()`` no pasa por ``delete()`` por instancia** — en
   ``_remove_work_entries`` el guard de validadas (``@api.ondelete``) se
   replica explícito antes del borrado (la fuente también revienta ahí:
   su ``unlink`` dispara ``_unlink_except_validated_work_entries``).
8. **``_get_fields_that_recompute_we``** devuelve los nombres de campo de
   ESTE árbol (``resource_calendar``, ``work_entry_source``) — los ``_id``
   de la fuente son la forma Odoo de los mismos campos.
"""
from datetime import datetime, time, timezone as dt_timezone

import fields
import models

from addons.hr_work_entry.models.hr_work_entry import HrWorkEntry
from addons.hr_work_entry.models.hr_work_entry_type import (
    ATTENDANCE_TYPE_CODE,
    HrWorkEntryType,
)
from addons.resource.models.resource_calendar_leaves import ResourceCalendarLeaves
from django.utils import timezone
from orm.environments import get_current_companies
from orm.method_chain import chain_method, extend_list
from orm.model_classes import extend_model

#: ``code`` de ``hr_work_entry.work_entry_type_overtime`` /
#: ``work_entry_type_leave`` en la data de la fuente (D-3).
OVERTIME_TYPE_CODE = 'OVERTIME'
LEAVE_TYPE_CODE = 'LEAVE100'

#: ≙ el ``Selection`` inline de ``work_entry_source`` (``:27``) — la fuente
#: sólo declara ``calendar``; ``attendance``/``planning`` los añaden sus
#: addons puente (no portados).
WORK_ENTRY_SOURCES = [('calendar', 'Working Schedule')]


def _generation_boundary_today():
    """Default de ``date_generated_from``/``date_generated_to`` — ≙
    ``datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)``
    (``:21``, ``:24``); reloj aware del árbol (USE_TZ=True). Función nombrada
    (el serializador de migraciones rechaza lambdas)."""
    return timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Property — compute sin store
# ---------------------------------------------------------------------------

def _compute_work_entry_source_calendar_invalid(self):
    """≙ ``work_entry_source_calendar_invalid`` /
    ``_compute_work_entry_source_calendar_invalid`` (``odoo19c:
    hr_work_entry/models/hr_version.py:34-42``)."""
    return self.work_entry_source == 'calendar' and not self.resource_calendar_id


# ---------------------------------------------------------------------------
# Métodos portados
# ---------------------------------------------------------------------------

def _get_default_work_entry_type_id(self):
    """≙ ``_get_default_work_entry_type_id`` (``:44-47``) — D-2, D-3."""
    return (
        HrWorkEntryType.objects.filter(code=ATTENDANCE_TYPE_CODE)
        .values_list('pk', flat=True).first()
        or False
    )


def _get_default_work_entry_type_overtime_id(self):
    """≙ ``_get_default_work_entry_type_overtime_id`` (``:49-52``) — D-2, D-3."""
    return (
        HrWorkEntryType.objects.filter(code=OVERTIME_TYPE_CODE)
        .values_list('pk', flat=True).first()
        or False
    )


def _get_leave_work_entry_type_dates(self, leave, date_from, date_to, employee):
    """≙ ``_get_leave_work_entry_type_dates`` (``:54-55``)."""
    return self._get_leave_work_entry_type(leave)


def _get_leave_work_entry_type(self, leave):
    """≙ ``_get_leave_work_entry_type`` (``:57-58``) — lee el campo que este
    mismo addon cuelga de ``resource.calendar.leaves``."""
    return leave.work_entry_type


def _get_more_vals_attendance_interval(self, interval):
    """≙ ``_get_more_vals_attendance_interval`` (``:61-62``) — hook para que
    los addons puente añadan valores (p. ej. planning_slot_id)."""
    return []


def _get_more_vals_leave_interval(self, interval, leaves):
    """≙ ``_get_more_vals_leave_interval`` (``:64-66``) — hook (p. ej.
    leave_id en hr_work_entry_holidays)."""
    return []


def _get_bypassing_work_entry_type_codes(self):
    """≙ ``_get_bypassing_work_entry_type_codes`` (``:68-69``)."""
    return []


def _get_interval_leave_work_entry_type(self, interval, leaves, bypassing_codes):
    """≙ ``_get_interval_leave_work_entry_type`` (``:71-82``) — el tipo de la
    ausencia que cubre el intervalo completo; el fallback ``env.ref(
    work_entry_type_leave)`` es la búsqueda por ``code`` (D-3)."""
    for leave in leaves:
        if interval[0] >= leave[0] and interval[1] <= leave[1] and leave[2]:
            interval_start = (
                interval[0].astimezone(dt_timezone.utc).replace(tzinfo=None)
            )
            interval_stop = (
                interval[1].astimezone(dt_timezone.utc).replace(tzinfo=None)
            )
            return self._get_leave_work_entry_type_dates(
                leave[2], interval_start, interval_stop, self.employee,
            )
    return HrWorkEntryType.objects.filter(code=LEAVE_TYPE_CODE).first()


def _get_sub_leave_domain(self):
    """≙ ``_get_sub_leave_domain`` (``:84-85``) — ``Domain`` → ``Q`` (D-4)."""
    return (
        models.Q(calendar__isnull=True)
        | models.Q(calendar_id=self.resource_calendar_id)
    )


def _get_leave_domain(self, start_dt, end_dt):
    """≙ ``_get_leave_domain`` (``:87-94``) — ``Domain`` → ``Q`` (D-4);
    ``env.companies`` → ``get_current_companies`` (mismo canal)."""
    resource_id = (
        self.employee.resource_id
        if self.employee_id and self.employee.resource_id else None
    )
    domain = (
        (models.Q(resource__isnull=True) | models.Q(resource_id=resource_id))
        & models.Q(date_from__lte=end_dt)
        & models.Q(date_to__gte=start_dt)
        & (models.Q(company__isnull=True)
           | models.Q(company_id__in=get_current_companies() or ()))
    )
    return domain & self._get_sub_leave_domain()


def _get_resource_calendar_leaves(self, start_dt, end_dt):
    """≙ ``_get_resource_calendar_leaves`` (``:96-97``) — queryset (D-4)."""
    return ResourceCalendarLeaves.objects.filter(
        self._get_leave_domain(start_dt, end_dt),
    )


def _get_interval_work_entry_type(self, interval):
    """≙ ``_get_interval_work_entry_type`` (``:139-143``) — el tipo del
    intervalo: el de sus tramos de asistencia si lo declaran, si no el
    default (asistencia). El ``interval[2]`` es el tercer miembro de la
    tupla de intervalo (tramos ``resource.calendar.attendance``)."""
    records = interval[2]
    if records is not None and not hasattr(records, '__iter__'):
        records = [records]
    for record in (records or []):
        work_entry_type = getattr(record, 'work_entry_type', None)
        if work_entry_type is not None:
            return work_entry_type
    default_id = self._get_default_work_entry_type_id()
    if default_id:
        return HrWorkEntryType.objects.filter(pk=default_id).first()
    return None


def _get_valid_leave_intervals(self, attendances, interval):
    """≙ ``_get_valid_leave_intervals`` (``:145-147``) — hook."""
    return [interval]


def _get_whitelist_fields_from_template(cls):
    """≙ ``_get_whitelist_fields_from_template`` (``:149-151``) — la mitad de
    este addon; el ``super()`` lo aporta ``combine=extend_list``."""
    return ['work_entry_source']


def _get_real_attendance_work_entry_vals(self, intervals):
    """≙ ``_get_real_attendance_work_entry_vals`` (``:153-170``) — vals de
    entrada de trabajo por intervalo de asistencia. Las claves
    ``date_start``/``date_stop`` son las de la fuente: las consume el
    postprocess (bloqueado), que las convierte a ``date``+``duration``."""
    vals = []
    employee = self.employee
    for interval in intervals:
        work_entry_type = self._get_interval_work_entry_type(interval)
        # Todos los beneficios generados aquí usan datetimes convertidos
        # desde la zona horaria del empleado (comentario verbatim, :161).
        vals += [dict([
            ('name', '%s: %s' % (
                work_entry_type.name if work_entry_type else '', employee.name,
            )),
            ('date_start',
             interval[0].astimezone(dt_timezone.utc).replace(tzinfo=None)),
            ('date_stop',
             interval[1].astimezone(dt_timezone.utc).replace(tzinfo=None)),
            ('work_entry_type_id', work_entry_type.pk if work_entry_type else None),
            ('employee_id', employee.pk),
            ('version_id', self.pk),
            ('company_id', self.company_id),
        ] + self._get_more_vals_attendance_interval(interval))]
    return vals


def has_static_work_entries(self):
    """≙ ``has_static_work_entries`` (``:388-392``) — entradas estáticas =
    generadas desde el horario (vs. addons puente por asistencias)."""
    return self.work_entry_source == 'calendar'


def _generate_work_entries_postprocess_adapt_to_calendar(cls, vals):
    """≙ ``_generate_work_entries_postprocess_adapt_to_calendar``
    (``@api.model``, ``:499-503``)."""
    if 'work_entry_type_id' not in vals:
        return False
    entry_type = HrWorkEntryType.objects.filter(
        pk=vals['work_entry_type_id'],
    ).first()
    return bool(entry_type and entry_type.is_leave)


def _remove_work_entries(self):
    """≙ ``_remove_work_entries`` (``:626-644``) — borra las entradas fuera
    del periodo del contrato (tras mover sus fechas). D-5 (instancia), D-7
    (guard de validadas replicado antes del ``delete()`` de queryset)."""
    to_unlink = HrWorkEntry.objects.none()
    date_start = self.date_start
    if date_start and self.date_generated_from is not None \
            and self.date_generated_from.date() < date_start:
        before_start = HrWorkEntry.objects.filter(
            date__lt=date_start, version=self,
        )
        if before_start.exists():
            self.date_generated_from = datetime.combine(
                date_start, time.min, tzinfo=dt_timezone.utc,
            )
            self.save(update_fields=['date_generated_from'])
            to_unlink = to_unlink | before_start
    date_end = self.date_end
    if date_end and self.date_generated_to is not None \
            and self.date_generated_to.date() > date_end:
        after_end = HrWorkEntry.objects.filter(
            date__gt=date_end, version=self,
        )
        if after_end.exists():
            self.date_generated_to = datetime.combine(
                date_end, time.max, tzinfo=dt_timezone.utc,
            )
            self.save(update_fields=['date_generated_to'])
            to_unlink = to_unlink | after_end
    if to_unlink.filter(state='validated').exists():
        # ≙ el @api.ondelete que el unlink de la fuente dispararía.
        first_validated = to_unlink.filter(state='validated').first()
        first_validated._unlink_except_validated_work_entries()
    to_unlink.delete()


def _cancel_work_entries(self):
    """≙ ``_cancel_work_entries`` (``:646-663``) — borra las entradas no
    validadas del periodo de esta versión (al borrarla). D-5: instancia (el
    ``Domain.OR`` por lote de la fuente es una llamada por versión)."""
    date_start = self.date_start
    if not date_start:
        return
    entries = HrWorkEntry.objects.filter(
        version=self, date__gte=date_start,
    ).exclude(state='validated')
    if self.date_end:
        entries = entries.filter(date__lte=self.date_end)
    entries.delete()


def _get_fields_that_recompute_we(self):
    """≙ ``_get_fields_that_recompute_we`` (``:694-696``) — D-8: nombres de
    campo de este árbol."""
    return ['resource_calendar', 'work_entry_source']


# ---------------------------------------------------------------------------
# Cableado
# ---------------------------------------------------------------------------

def _wire_whitelist_chain(model):
    """Encadena ``_get_whitelist_fields_from_template`` (classmethod en la
    base) con ``combine=extend_list`` — ≙ ``super() + [...]`` (``:151``)."""
    chain_method(
        model, '_get_whitelist_fields_from_template',
        classmethod(_get_whitelist_fields_from_template),
        combine=extend_list,
    )


def apply_hr_work_entry_hr_version_extensions():
    """Cuelga sobre ``hr.version`` lo que ``hr_work_entry`` le añade — ≙
    ``_inherit``."""
    extend_model(
        'hr', 'HrVersion',
        campos={
            'date_generated_from': fields.Datetime(
                verbose_name='Generated From',
                default=_generation_boundary_today,
                help_text='Odoo date_generated_from (required, readonly, '
                          'groups=hr.group_hr_user, tracking — D-1).',
            ),
            'date_generated_to': fields.Datetime(
                verbose_name='Generated To',
                default=_generation_boundary_today,
                help_text='Odoo date_generated_to (required, readonly, '
                          'groups=hr.group_hr_user, tracking — D-1).',
            ),
            'last_generation_date': fields.Date(
                null=True, blank=True, verbose_name='Last Generation Date',
                help_text='Odoo last_generation_date (readonly, '
                          'groups=hr.group_hr_user, tracking — D-1).',
            ),
            'work_entry_source': fields.Selection(
                choices=WORK_ENTRY_SOURCES, default='calendar',
                help_text='Defines the source for work entries generation. '
                          'Working Schedule: Work entries will be generated '
                          'from the working hours below. Attendances/Planning '
                          'los añaden sus addons puente (no portados).',
            ),
        },
        propiedades={
            'work_entry_source_calendar_invalid':
                _compute_work_entry_source_calendar_invalid,
        },
        metodos={
            '_get_default_work_entry_type_id': _get_default_work_entry_type_id,
            '_get_default_work_entry_type_overtime_id':
                _get_default_work_entry_type_overtime_id,
            '_get_leave_work_entry_type_dates': _get_leave_work_entry_type_dates,
            '_get_leave_work_entry_type': _get_leave_work_entry_type,
            '_get_more_vals_attendance_interval': _get_more_vals_attendance_interval,
            '_get_more_vals_leave_interval': _get_more_vals_leave_interval,
            '_get_bypassing_work_entry_type_codes':
                _get_bypassing_work_entry_type_codes,
            '_get_interval_leave_work_entry_type':
                _get_interval_leave_work_entry_type,
            '_get_sub_leave_domain': _get_sub_leave_domain,
            '_get_leave_domain': _get_leave_domain,
            '_get_resource_calendar_leaves': _get_resource_calendar_leaves,
            '_get_interval_work_entry_type': _get_interval_work_entry_type,
            '_get_valid_leave_intervals': _get_valid_leave_intervals,
            '_get_real_attendance_work_entry_vals':
                _get_real_attendance_work_entry_vals,
            'has_static_work_entries': has_static_work_entries,
            '_generate_work_entries_postprocess_adapt_to_calendar':
                classmethod(_generate_work_entries_postprocess_adapt_to_calendar),
            '_remove_work_entries': _remove_work_entries,
            '_cancel_work_entries': _cancel_work_entries,
            '_get_fields_that_recompute_we': _get_fields_that_recompute_we,
        },
        luego=_wire_whitelist_chain,
    )
