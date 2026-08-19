"""``hr.work.entry`` — una entrada de trabajo (día + duración) de un empleado.

Adaptación de Odoo hr_work_entry/models/hr_work_entry.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 336 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03).

Atributos de clase: 4/4 — ``_name``/``_description``/``_order`` verbatim;
``_contract_date_start_stop_idx`` (``:52-53``, ``models.Index`` parcial
``(version_id, date) WHERE state IN ('draft','validated')``) →
``Meta.indexes`` con ``condition=`` y el nombre de la fuente conservado
(``contract_date_start_stop_idx``, 28 caracteres — sin el guion bajo inicial,
que en el objeto de tabla de la referencia es sintaxis de declaración, no
parte del nombre SQL). La fuente **no** usa ``EXCLUDE`` de PostgreSQL —
medido: ``grep -rn EXCLUDE models/ wizard/`` → 0 hits (en 19 el solape se
vigila por SQL de agregación, ``_mark_conflicting_work_entries``).

Porte símbolo por símbolo — 18 campos + 24 métodos
===================================================

Campos (18):

- **Columna (10):** ``name`` ``active`` ``employee_id``→``employee``
  ``version_id``→``version`` ``date`` ``duration``
  ``work_entry_type_id``→``work_entry_type`` ``state`` ``company_id``→
  ``company`` ``amount_rate``.
- **Property (7)** — ``related=``/compute (D-1): ``work_entry_source``
  (``:27``), ``display_code`` (``:35``), ``code`` (``:36``),
  ``external_code`` (``:37``), ``color`` (``:38``), ``department_id``
  (``:48``, related con ``store=True`` — la property no puede
  desincronizarse, que es lo que el store compraba), ``country_id``
  (``:50``).
- **Property (1)** — ``conflict`` (``:47``, ``compute='_compute_conflict'
  store=True``): es ``state == 'conflict'`` literal; columna espejo sin
  posibilidad de divergencia → property (D-1). El "para ordenar primero"
  del comentario fuente se logra con ``order_by`` sobre ``state`` en el
  queryset consumidor.

Métodos (24) — 17 portados, 3 divergencia declarada, 4 BLOQUEADOS:

- **Portados (17):** ``_check_duration``, ``_compute_display_name`` (→
  property ``display_name``), ``_compute_name``, ``_compute_conflict`` (→
  property ``conflict``), ``_set_current_contract``, ``action_validate``,
  ``action_split``, ``_check_if_error`` (con cobertura declarada — ver D-6),
  ``_mark_conflicting_work_entries``, ``_get_leaves_entries_outside_schedule``,
  ``_mark_already_validated_days``, ``create`` (→ mitad de alta de
  ``save()``, D-4), ``_unlink_except_validated_work_entries`` (+ ``unlink``
  → ``delete()``, D-5), ``_reset_conflicting_state``, ``_error_checking``,
  ``_get_work_entry_type_domain`` (D-7).
- **Divergencia declarada (3):** ``_onchange_version_id`` (``:80-91``) — el
  onchange es mecánica del cliente Odoo; su efecto (resolver la versión
  desde empleado+fecha) vive en la mitad de alta de ``save()`` vía
  ``_set_current_contract``. ``write`` (``:261-277``) — el acoplamiento
  state↔active y el salto de ``_error_checking`` dependen del dict ``vals``
  (saber QUÉ cambió), que ``save()`` no recibe; se porta la mitad
  determinista en ``save()`` (``state=='cancelled'`` ⇒ ``active=False``,
  ``state=='draft'`` ⇒ ``active=True``, verbatim de ``:263-267``) y la
  re-verificación de conflictos la envuelve la capa de servicio con
  ``_error_checking``. ``_search_country_id`` (``:335-336``) — ``search=``
  es maquinaria de dominio de Odoo; la ruta de queryset equivalente es
  ``.filter(employee__company__country=...)``. NOTA (hallazgo H-1 del
  resumen): la fuente busca por ``company_id.partner_id.country_id`` pero el
  ``related`` del campo lee ``company_id.country_id`` — dos rutas distintas.
- **BLOQUEADOS (4) por el motor de intervalos** (``resource: models/
  resource_calendar.py``, sección "Qué NO se porta" — ``Intervals`` +
  ``_attendance_intervals_batch`` + ``_get_unusual_days`` DEFERIDOS):
  ``get_unusual_days`` (``:101-107``), ``_mark_leaves_outside_schedule``
  (``:184-211``), ``_to_intervals`` (``:231-234``), ``_from_intervals``
  (``:236-238``). Se desbloquean con ese motor — misma condición de cierre
  que su DEFERIDO (un UC de disponibilidad/agenda que lo consuma).

Divergencias declaradas
========================

1. **related/compute → property** — sin ``@api.depends`` no hay recómputo
   disparado; la property recalcula en cada lectura (patrón
   ``hr_version.py``).
2. **Recordset → queryset/lista.** Los métodos de lote de la fuente
   (``self`` = recordset) son ``@classmethod`` que reciben las entradas como
   argumento (``entries``); los de un registro son métodos de instancia.
3. **``self.env.cr.execute`` (SQL crudo, ``:155-176``) → agregación ORM** en
   ``_mark_conflicting_work_entries`` — mismo corte (GROUP BY empleado+día,
   HAVING fuera de (0, 24]), sin SQL literal; el ``flush_model`` de la
   fuente no aplica (sin caché de recordset que volcar).
4. **``create(vals_list)`` → ``save()`` por instancia** — la mitad de alta
   (resolver versión, ``amount_rate`` desde el tipo, compañía desde el
   empleado) corre en ``save()`` cuando el registro es nuevo; el
   ``_check_if_error`` posterior al alta lo invoca la capa de servicio sobre
   el lote (por lote, como la fuente — no por fila).
5. **``unlink``/``@api.ondelete`` → ``delete()``** — el guard
   ``_unlink_except_validated_work_entries`` corre en ``delete()`` y el
   borrado queda envuelto en ``_error_checking`` (≙ ``unlink``, ``:284-287``).
6. **``_check_if_error`` con cobertura declarada:** de sus tres
   verificaciones, corre ``_mark_conflicting_work_entries`` y
   ``_mark_already_validated_days``; ``_mark_leaves_outside_schedule`` está
   BLOQUEADO (motor de intervalos) y se reconecta al desbloquearse.
7. **``env.companies`` → ``orm.environments.get_current_companies()``** en
   ``_get_work_entry_type_domain``, que devuelve un ``models.Q`` sobre
   ``HrWorkEntryType`` (dominio → ORM).
8. **``sudo().with_context(hr_work_entry_no_check=True)``** →
   ``orm.environments.get_context()`` para leer la bandera; el re-entrado
   con la bandera puesta no hace falta (los checks internos son consultas
   directas, no ``search`` re-verificado).
"""
from contextlib import contextmanager
from datetime import timedelta

import fields
import models

from addons.base.models import ResCompany, TimeStampedModel
from addons.hr.models import HrEmployee
from addons.hr_work_entry.models.hr_work_entry_type import HrWorkEntryType
from django.db import OperationalError
from exceptions import UserError, ValidationError
from orm.environments import get_context, get_current_companies, get_current_company
from tools.float_utils import float_compare
from tools.translate import _


def _default_work_entry_type():
    """Default de ``work_entry_type`` — ≙ ``search([], limit=1)`` (``:33``).

    Función nombrada (el serializador de migraciones rechaza lambdas);
    devuelve el PK del primer tipo del catálogo, o ``None`` si está vacío.
    """
    return (
        HrWorkEntryType.objects.order_by('pk')
        .values_list('pk', flat=True).first()
    )


class HrWorkEntry(TimeStampedModel):
    """``hr.work.entry`` — un día de trabajo/ausencia de un empleado, con su
    tipo, duración en horas y estado de validación."""

    _name = 'hr.work.entry'
    _description = 'HR Work Entry'
    _order = 'create_date'

    STATES = [
        ('draft', 'New'),
        ('conflict', 'In Conflict'),
        ('validated', 'In Payslip'),
        ('cancelled', 'Cancelled'),
    ]

    name = fields.Char(max_length=255, blank=True, default='')
    active = fields.Boolean(default=True)
    employee = fields.Many2one(
        'hr.HrEmployee', on_delete=models.CASCADE, db_index=True,
        related_name='work_entries', verbose_name='Empleado',
        help_text='Odoo employee_id (required, index). DIVERGENCIA: sin el '
                  'domain= de compañía (filtro de formulario; lo aplica DRF).',
    )
    version = fields.Many2one(
        'hr.HrVersion', on_delete=models.CASCADE, db_index=True,
        related_name='work_entries', verbose_name='Employee Record',
        help_text='Odoo version_id (required, index).',
    )
    date = fields.Date(help_text='Odoo date (required).')
    duration = fields.Float(default=8, verbose_name='Duration')
    work_entry_type = fields.Many2one(
        HrWorkEntryType, on_delete=models.SET_NULL, null=True, blank=True,
        db_index=True, related_name='work_entries',
        default=_default_work_entry_type,
        help_text='Odoo work_entry_type_id. El domain= dinámico es '
                  '_get_work_entry_type_domain (D-7).',
    )
    state = fields.Selection(max_length=10, choices=STATES, default='draft')
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.PROTECT, null=True, blank=True,
        related_name='work_entries', verbose_name='Company',
        default=get_current_company,
        help_text='Odoo company_id (required, readonly, default=env.company '
                  '→ get_current_company). Nullable aquí porque el default de '
                  'sesión puede ser None fuera de una petición; la mitad de '
                  'alta de save() lo completa desde el empleado (≙ create).',
    )
    amount_rate = fields.Float(
        null=True, blank=True, verbose_name='Pay rate',
        help_text='Odoo amount_rate. None = sin fijar; la mitad de alta de '
                  'save() lo toma del tipo (≙ create, :245-250).',
    )

    class Meta:
        db_table = 'hr_work_entry'
        ordering = ['created_at']  # ≙ _order = 'create_date'
        verbose_name = 'Entrada de trabajo'
        verbose_name_plural = 'Entradas de trabajo'
        indexes = [
            # ≙ ``_contract_date_start_stop_idx`` (``:52-53``): "FROM 7s by
            # query to 2ms (with 2.6 millions entries)" — índice parcial
            # sobre (version, date) para los estados vivos.
            models.Index(
                fields=['version', 'date'],
                condition=models.Q(state__in=('draft', 'validated')),
                name='contract_date_start_stop_idx',
            ),
        ]

    def __str__(self):
        return self.display_name

    # ------------------------------------------------------------------
    # Propiedades — related / compute (D-1)
    # ------------------------------------------------------------------

    @property
    def work_entry_source(self):
        """≙ ``work_entry_source`` (``related='version_id.work_entry_source'``,
        ``:27``)."""
        return self.version.work_entry_source if self.version_id else None

    @property
    def display_code(self):
        """≙ ``display_code`` (``related='work_entry_type_id.display_code'``,
        ``:35``)."""
        return self.work_entry_type.display_code if self.work_entry_type_id else ''

    @property
    def code(self):
        """≙ ``code`` (``related='work_entry_type_id.code'``, ``:36``)."""
        return self.work_entry_type.code if self.work_entry_type_id else ''

    @property
    def external_code(self):
        """≙ ``external_code`` (``related='work_entry_type_id.external_code'``,
        ``:37``)."""
        return self.work_entry_type.external_code if self.work_entry_type_id else ''

    @property
    def color(self):
        """≙ ``color`` (``related='work_entry_type_id.color'``, ``:38``)."""
        return self.work_entry_type.color if self.work_entry_type_id else 0

    @property
    def conflict(self):
        """≙ ``conflict`` / ``_compute_conflict`` (``:47``, ``:75-78``) —
        property en vez de compute+store (cabecera, campo 'conflict')."""
        return self.state == 'conflict'

    @property
    def department(self):
        """≙ ``department_id`` (``related='employee_id.department_id'``
        ``store=True``, ``:48``)."""
        return self.employee.department if self.employee_id else None

    @property
    def country(self):
        """≙ ``country_id`` (``related='employee_id.company_id.country_id'``,
        ``:50``). Su ``search=`` es ``_search_country_id`` — divergencia
        declarada en la cabecera."""
        if self.employee_id and self.employee.company_id:
            return self.employee.company.country
        return None

    @property
    def display_name(self):
        """≙ ``_compute_display_name`` (``:61-65``)."""
        duration = str(timedelta(hours=self.duration or 0)).split(':')
        type_name = self.work_entry_type.name if self.work_entry_type_id else ''
        return '%s - %sh%s' % (type_name, duration[0], duration[1])

    # ------------------------------------------------------------------
    # Validaciones y helpers de un registro
    # ------------------------------------------------------------------

    def _check_duration(self):
        """≙ ``_check_duration`` (``@api.constrains('duration')``, ``:55-59``)."""
        if (float_compare(self.duration or 0, 0, 3) <= 0
                or float_compare(self.duration or 0, 24, 3) > 0):
            raise ValidationError(
                'Duration must be positive and cannot exceed 24 hours.'
            )

    def clean(self):
        super().clean()
        self._check_duration()

    def _compute_name(self):
        """≙ ``_compute_name`` (``:67-73``) — asigna ``name`` y lo devuelve.

        NOTA (hallazgo H-1 del resumen): en la fuente el campo ``name``
        (``:23``) NO declara ``compute='_compute_name'``, así que su
        ``@api.depends`` no dispara nada — aquí es un helper explícito con la
        misma lógica.
        """
        if not self.employee_id:
            self.name = _('Undefined')
        else:
            type_name = (self.work_entry_type.name
                         if self.work_entry_type_id else None)
            self.name = '%s: %s' % (
                type_name or _('Undefined Type'), self.employee.name,
            )
        return self.name

    @classmethod
    def _set_current_contract(cls, vals):
        """≙ ``_set_current_contract`` (``:93-99``) — completa
        ``version_id`` en un dict de vals desde empleado + fecha."""
        if not vals.get('version_id') and vals.get('date') and vals.get('employee_id'):
            employee = HrEmployee.objects.get(pk=vals['employee_id'])
            active_version = employee._get_version(vals['date'])
            return dict(vals, version_id=active_version.pk if active_version else None)
        return vals

    def action_split(self, vals):
        """≙ ``action_split`` (``:122-136``) — parte esta entrada en dos.

        ``self.copy()`` → duplicado por ``pk=None`` (mismo efecto: una fila
        nueva con los valores de ésta, sobreescritos por ``vals``).
        """
        if self.duration < 1:
            raise UserError("You can't split a work entry with less than 1 hour.")
        split_duration = vals['duration']
        if self.duration <= split_duration:
            raise UserError(
                'Split work entry duration has to be less than the existing '
                'work entry duration.'
            )
        self.duration -= split_duration
        self.save()
        split_work_entry = HrWorkEntry.objects.get(pk=self.pk)
        split_work_entry.pk = None
        split_work_entry._state.adding = True
        for field_name, value in vals.items():
            setattr(split_work_entry, field_name, value)
        split_work_entry.save()
        return split_work_entry.pk

    # ------------------------------------------------------------------
    # Verificación de conflictos — métodos de lote (D-2)
    # ------------------------------------------------------------------

    @classmethod
    def action_validate(cls, entries):
        """≙ ``action_validate`` (``:109-120``) — valida el lote; si hay
        conflictos, los marca y devuelve ``False``."""
        pending = cls.objects.filter(
            pk__in=[e.pk for e in entries],
        ).exclude(state='validated')
        if not cls._check_if_error(list(pending)):
            pending.update(state='validated')
            return True
        return False

    @classmethod
    def _check_if_error(cls, entries):
        """≙ ``_check_if_error`` (``:138-146``) — cobertura declarada D-6:
        ``_mark_leaves_outside_schedule`` (``:144``) NO se invoca (BLOQUEADO
        por el motor de intervalos); se reconecta al desbloquearse."""
        entries = list(entries)
        if not entries:
            return False
        undefined_type = [e for e in entries if not e.work_entry_type_id]
        cls.objects.filter(
            pk__in=[e.pk for e in undefined_type],
        ).update(state='conflict')
        dates = [e.date for e in entries]
        conflict = cls._mark_conflicting_work_entries(entries, min(dates), max(dates))
        already_validated_days = cls._mark_already_validated_days(entries)
        return bool(undefined_type) or conflict or already_validated_days

    @classmethod
    def _mark_conflicting_work_entries(cls, entries, start, stop):
        """≙ ``_mark_conflicting_work_entries`` (``:148-179``) — marca en
        conflicto los días cuyo total por empleado sale de (0, 24] horas.

        D-3: el SQL crudo de la fuente (CTE ``excessive_days``) es la misma
        agregación expresada en ORM.
        """
        employee_ids = {e.employee_id for e in entries if e.employee_id}
        if not employee_ids:
            return False
        excessive_days = (
            cls.objects.filter(
                active=True, date__range=(start, stop),
                employee_id__in=employee_ids,
            )
            .values('employee_id', 'date')
            .annotate(total=models.Sum('duration'))
            .filter(models.Q(total__lte=0) | models.Q(total__gt=24))
        )
        day_filter = models.Q(pk__in=[])
        for day in excessive_days:
            day_filter |= models.Q(employee_id=day['employee_id'], date=day['date'])
        conflict_qs = cls.objects.filter(active=True).filter(day_filter)
        conflict_ids = list(conflict_qs.values_list('pk', flat=True))
        cls.objects.filter(pk__in=conflict_ids).update(state='conflict')
        return bool(conflict_ids)

    @classmethod
    def _get_leaves_entries_outside_schedule(cls, entries):
        """≙ ``_get_leaves_entries_outside_schedule`` (``:181-182``)."""
        return [
            e for e in entries
            if e.work_entry_type_id and e.work_entry_type.is_leave
            and e.state not in ('validated', 'cancelled')
        ]

    @classmethod
    def _mark_already_validated_days(cls, entries):
        """≙ ``_mark_already_validated_days`` (``:213-229``) — marca en
        conflicto las entradas de días que ya tienen entradas validadas."""
        entries = list(entries)
        dates = [e.date for e in entries]
        validated = cls.objects.filter(
            state='validated',
            date__lte=max(dates), date__gte=min(dates),
            company_id=get_current_company(),
        )
        validated_days = {(v.employee_id, v.date) for v in validated}
        invalid_ids = [
            e.pk for e in entries
            if (e.employee_id, e.date) in validated_days
        ]
        cls.objects.filter(pk__in=invalid_ids).update(state='conflict')
        return bool(invalid_ids)

    @classmethod
    def _reset_conflicting_state(cls, entries):
        """≙ ``_reset_conflicting_state`` (``:289-290``)."""
        cls.objects.filter(
            pk__in=[e.pk for e in entries], state='conflict',
        ).update(state='draft')

    @classmethod
    @contextmanager
    def _error_checking(cls, start=None, stop=None, skip=False,
                        employee_ids=False, entries=None):
        """≙ ``_error_checking`` (``:292-328``) — context manager de
        verificación de conflictos sobre un rango de fechas.

        D-2: el ``self`` recordset de la fuente es el parámetro ``entries``
        (de él salen los defaults de ``start``/``stop``). D-8: la bandera
        ``hr_work_entry_no_check`` se lee de ``orm.environments.get_context``.
        """
        work_entries = []
        try:
            skip = skip or bool(get_context().get('hr_work_entry_no_check', False))
            entry_dates = [e.date for e in (entries or [])]
            start = start or (min(entry_dates) if entry_dates else False)
            stop = stop or (max(entry_dates) if entry_dates else False)
            if not skip and start and stop:
                in_range = cls.objects.filter(
                    date__lte=stop, date__gte=start,
                ).exclude(state__in=('validated', 'cancelled'))
                if employee_ids:
                    in_range = in_range.filter(employee_id__in=list(employee_ids))
                work_entries = list(in_range)
                cls._reset_conflicting_state(work_entries)
            yield
        except OperationalError:
            # El cursor murió: no intentar usarlo o taparíamos la excepción
            # raíz con un "current transaction is aborted, ..." (verbatim de
            # la fuente, :319-323).
            skip = True
            raise
        finally:
            if not skip and start and stop:
                # Las entradas nuevas se atienden en la mitad de alta de
                # save(); no hace falta recargar (≙ :324-328).
                alive = cls.objects.filter(pk__in=[e.pk for e in work_entries])
                cls._check_if_error(list(alive))

    # ------------------------------------------------------------------
    # Alta / escritura / borrado (D-4, D-5, y la mitad determinista de write)
    # ------------------------------------------------------------------

    def save(self, *args, **kwargs):
        """Mitad de alta de ``create`` (``:240-259``) + mitad determinista de
        ``write`` (``:263-267``) — divergencias D-4 y de cabecera."""
        if self._state.adding:
            # ≙ _set_current_contract sobre vals (:242)
            if not self.version_id and self.date and self.employee_id:
                active_version = self.employee._get_version(self.date)
                if active_version:
                    self.version = active_version
            # ≙ amount_rate desde el tipo (:244-250)
            if self.amount_rate is None and self.work_entry_type_id:
                self.amount_rate = self.work_entry_type.amount_rate
            # ≙ company desde el empleado (:251-256)
            if not self.company_id and self.employee_id:
                self.company = self.employee.company
        # ≙ write :263-267 — la dirección state → active
        if self.state == 'cancelled':
            self.active = False
        elif self.state == 'draft':
            self.active = True
        super().save(*args, **kwargs)

    def _unlink_except_validated_work_entries(self):
        """≙ ``_unlink_except_validated_work_entries`` (``@api.ondelete``,
        ``:279-282``)."""
        if self.state == 'validated':
            raise UserError(_("This work entry is validated. You can't delete it."))

    def delete(self, *args, **kwargs):
        """≙ ``unlink`` (``:284-287``) + el guard ``@api.ondelete`` (D-5)."""
        self._unlink_except_validated_work_entries()
        employee_ids = [self.employee_id] if self.employee_id else []
        with type(self)._error_checking(entries=[self], employee_ids=employee_ids):
            return super().delete(*args, **kwargs)

    # ------------------------------------------------------------------
    # Dominios (D-7)
    # ------------------------------------------------------------------

    @classmethod
    def _get_work_entry_type_domain(cls):
        """≙ ``_get_work_entry_type_domain`` (``:330-333``) — devuelve el
        ``models.Q`` para filtrar ``HrWorkEntryType`` según los países de las
        compañías activadas (``env.companies`` → ``get_current_companies``)."""
        country_ids = set(
            ResCompany.objects.filter(
                pk__in=get_current_companies() or (),
                country__isnull=False,
            ).values_list('country_id', flat=True)
        )
        if len(country_ids) > 1:
            return models.Q(country__isnull=True)
        return models.Q(country__isnull=True) | models.Q(country_id__in=country_ids)
