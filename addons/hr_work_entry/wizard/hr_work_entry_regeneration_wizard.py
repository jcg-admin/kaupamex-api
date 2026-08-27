"""``hr.work.entry.regeneration.wizard`` — regenerar entradas de trabajo.

Adaptación de Odoo hr_work_entry/wizard/hr_work_entry_regeneration_wizard.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 129 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03).

``TransientModel`` → clase sin tabla con classmethods (patrón
``hr/wizard/hr_departure_wizard.py`` / ``account_debit_note``): el estado del
wizard (empleados, rango de fechas) lo pasa el llamador como argumentos.

Porte símbolo por símbolo — 2 atributos + 10 campos + 10 métodos
=================================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_name`` / ``_description`` (``:11-12``)
     - portados verbatim
   * - ``date_from`` (``:18``) / ``date_to`` (``:19-20``) /
       ``employee_ids`` (``:21-22``)
     - resueltos con otra forma — argumentos de los classmethods; sus
       defaults de ``context`` (``date_start``/``date_end``) eran mecánica
       del cliente; el ``domain=`` de compañías lo aplica DRF con
       ``get_current_companies`` (mismo criterio que
       ``hr_departure_wizard._get_domain_employee_ids``)
   * - ``earliest_available_date`` (``:14``) /
       ``latest_available_date`` (``:16``)
     - portados — ``_compute_earliest_available_date(employees)`` /
       ``_compute_latest_available_date(employees)`` (D-2)
   * - ``earliest_available_date_message`` (``:15``) /
       ``latest_available_date_message`` (``:17``)
     - resueltos con otra forma — son el retorno de ``_check_dates`` (eran
       columnas ``store=False`` que el onchange escribía para la UI)
   * - ``validated_work_entry_employee_ids`` (``:23-24``)
     - portado — ``_compute_validated_work_entry_employee_ids(employees,
       date_from, date_to)`` devuelve el queryset de empleados
   * - ``search_criteria_completed`` (``:25``) / ``valid`` (``:26``)
     - portados — ``_compute_search_criteria_completed`` /
       ``_compute_valid`` devuelven el booleano
   * - ``_compute_date_to`` (``:28-31``)
     - portado — D-1 (aritmética de calendario, sin dateutil)
   * - ``_check_dates`` (``:70-85``)
     - portado — el ``@api.onchange`` es mecánica del cliente; aquí es un
       classmethod puro que normaliza el rango y devuelve los mensajes
   * - ``_date_to_string`` (``:87-92``)
     - portado — D-3 (ISO 8601, sin ``res.lang`` de sesión)
   * - ``_work_entry_fields_to_nullify`` (``:94-95``)
     - portado verbatim
   * - ``regenerate_work_entries`` (``:97-129``)
     - **Bloqueado por ``generate_work_entries``** (``hr.employee`` →
       ``hr.version``), a su vez bloqueado por el motor de intervalos
       (``resource: models/resource_calendar.py``, "Qué NO se porta").
       Ambas ramas del método (con y sin ``slots``) terminan en esa
       llamada; la agrupación de ``slots`` en rangos de fechas contiguas
       (``:116-126``, python puro) llega gratis al desbloquearse. Misma
       condición de cierre que el motor.

Divergencias declaradas
========================

1. **``relativedelta(months=+1, day=1, days=-1)`` → aritmética de
   calendario** (``calendar.monthrange``) — dateutil NO es dependencia
   (medido ``grep -i dateutil uv.lock`` → 0; precedente
   ``base_automation.advance_date``). El resultado es el mismo: el último
   día del mes de ``date_from``.
2. **``employee_ids.version_ids.mapped(...)`` → agregación ORM** sobre
   ``HrVersion``; el ``Date`` del campo destino coacciona el ``Datetime``
   de la fuente — aquí el ``.date()`` es explícito.
3. **``res.lang._get_data(...).date_format`` → ``isoformat()``** — sin
   sesión de idioma a nivel de wizard (familia (b) de
   ``hr/models/hr_version.py``).
"""
import calendar

from addons.hr.models import HrEmployee, HrVersion
from addons.hr_work_entry.models.hr_work_entry import HrWorkEntry
from orm.models_transient import TransientModel


class HrWorkEntryRegenerationWizard(TransientModel):
    """El asistente de regeneración — ≙ ``hr.work.entry.regeneration.wizard``."""

    class Meta:
        abstract = True
        managed = False

    # ---- Atributos de clase de modelo — verbatim (``:11-12``) ----
    _name = 'hr.work.entry.regeneration.wizard'
    _description = 'Regenerate Employee Work Entries'

    @classmethod
    def _compute_date_to(cls, date_from):
        """≙ ``_compute_date_to`` (``:28-31``) — el último día del mes de
        ``date_from`` (D-1)."""
        if not date_from:
            return None
        last_day = calendar.monthrange(date_from.year, date_from.month)[1]
        return date_from.replace(day=last_day)

    @classmethod
    def _compute_earliest_available_date(cls, employees):
        """≙ ``_compute_earliest_available_date`` (``:33-37``) — D-2."""
        earliest = HrVersion.objects.filter(
            employee__in=list(employees),
            date_generated_from__isnull=False,
        ).order_by('date_generated_from').values_list(
            'date_generated_from', flat=True,
        ).first()
        return earliest.date() if earliest else None

    @classmethod
    def _compute_latest_available_date(cls, employees):
        """≙ ``_compute_latest_available_date`` (``:39-43``) — D-2."""
        latest = HrVersion.objects.filter(
            employee__in=list(employees),
            date_generated_to__isnull=False,
        ).order_by('-date_generated_to').values_list(
            'date_generated_to', flat=True,
        ).first()
        return latest.date() if latest else None

    @classmethod
    def _compute_validated_work_entry_employee_ids(cls, employees, date_from,
                                                   date_to):
        """≙ ``_compute_validated_work_entry_employee_ids`` (``:45-58``) —
        los empleados con entradas ya validadas en el rango (el
        ``_read_group`` de la fuente es el ``distinct`` de aquí)."""
        if not cls._compute_search_criteria_completed(
                employees, date_from, date_to):
            return HrEmployee.objects.none()
        employee_ids = HrWorkEntry.objects.filter(
            employee__in=list(employees),
            date__gte=date_from, date__lte=date_to,
            state='validated',
        ).values_list('employee_id', flat=True).distinct()
        return HrEmployee.objects.filter(pk__in=list(employee_ids))

    @classmethod
    def _compute_valid(cls, employees, date_from, date_to):
        """≙ ``_compute_valid`` (``:60-63``) — ¿queda al menos un empleado
        regenerable (sin entradas validadas en el rango)?"""
        if not cls._compute_search_criteria_completed(
                employees, date_from, date_to):
            return False
        validated = set(
            cls._compute_validated_work_entry_employee_ids(
                employees, date_from, date_to,
            ).values_list('pk', flat=True)
        )
        return len([e for e in employees if e.pk not in validated]) > 0

    @classmethod
    def _compute_search_criteria_completed(cls, employees, date_from, date_to):
        """≙ ``_compute_search_criteria_completed`` (``:65-68``)."""
        employees = list(employees)
        return bool(
            date_from and date_to and employees
            and cls._compute_earliest_available_date(employees)
            and cls._compute_latest_available_date(employees)
        )

    @classmethod
    def _check_dates(cls, employees, date_from, date_to):
        """≙ ``_check_dates`` (``@api.onchange``, ``:70-85``) — normaliza el
        rango (swap si viene invertido, clamp a las fechas disponibles) y
        devuelve ``(date_from, date_to, earliest_message, latest_message)``
        — los dos mensajes son los campos ``*_message`` de la fuente."""
        earliest_message = ''
        latest_message = ''
        if cls._compute_search_criteria_completed(employees, date_from, date_to):
            if date_from > date_to:
                date_from, date_to = date_to, date_from
            earliest = cls._compute_earliest_available_date(employees)
            latest = cls._compute_latest_available_date(employees)
            if earliest and date_from < earliest:
                date_from = earliest
                earliest_message = (
                    f'The earliest available date is {cls._date_to_string(earliest)}'
                )
            if latest and date_to > latest:
                date_to = latest
                latest_message = (
                    f'The latest available date is {cls._date_to_string(latest)}'
                )
        return date_from, date_to, earliest_message, latest_message

    @classmethod
    def _date_to_string(cls, date):
        """≙ ``_date_to_string`` (``@api.model``, ``:87-92``) — D-3: ISO
        8601 en vez del formato de ``res.lang`` del usuario."""
        if not date:
            return ''
        return date.isoformat()

    @classmethod
    def _work_entry_fields_to_nullify(cls):
        """≙ ``_work_entry_fields_to_nullify`` (``:94-95``) — los campos que
        ``_generate_work_entries`` anula al regenerar."""
        return ['active']
