"""Extensión de ``resource.calendar.leaves`` — el calendario sigue al
contrato (Odoo ``hr``).

Adaptación de Odoo hr/models/resource_calendar_leaves.py (odoo-tools@622ddc2a,
odoo19c:, LGPL-3, 33 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03).

La referencia sobreescribe ``_compute_calendar_id``: una ausencia cuyo
recurso pertenece a un empleado con versión vigente (``hr.version``) toma el
calendario **del contrato**, no el del recurso — y sólo si la fecha de la
ausencia cae dentro del periodo del contrato. Las ausencias sin versión caen
al cómputo del addon padre (``super()``).

Porte símbolo por símbolo — 1 de 1
===================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
     - Forma aquí
   * - ``_compute_calendar_id`` (``:14-33``)
     - portado
     - ``extend_model('resource', 'ResourceCalendarLeaves', metodos=…)``;
       nombre **verbatim**

``_inherit`` lo expresa ``extend_model`` (criterio de
``stock/models/res_users.py``); par de Django porque el destino no declara
``_name``.

Divergencias declaradas
========================

1. **El "super" es el inline de ``save()``.** El padre de este árbol no
   declara ``_compute_calendar_id`` como método: su lógica ("el calendario
   sigue al del recurso") vive inline en
   ``resource/models/resource_calendar_leaves.py::save()`` (``:93-97``).
   ``chain_method`` instala esta función sin previa que encadenar, así que la
   rama ``super(...remaining...)._compute_calendar_id()`` de la referencia se
   reproduce **dentro** de la función: la ausencia sin versión cae al
   calendario del recurso, que es exactamente lo que aquel inline hace.
2. **``grouped``/recordset → resolución por instancia.** La referencia agrupa
   un recordset por ``resource_id.employee_id.version_id``; aquí el método
   opera sobre UNA ausencia (mismo criterio que el resto de los métodos de
   instancia del árbol) y resuelve su empleado por el reverso real del mixin
   (``resource.hr_hremployee_resource_mixin_set``, el ``related_name`` que
   Django genera para ``ResourceMixin.resource`` en ``hr.employee``).
3. **``pytz`` → ``zoneinfo``** — misma decisión que
   ``resource/models/resource_calendar_leaves.py`` (que ya usa ``ZoneInfo``).
4. **No escribe si no hay cambio** — misma guarda que el patrón
   ``_compute_current_version_id`` de ``hr_employee.py``: el método asigna
   ``self.calendar`` y devuelve el calendario elegido; persiste quien llama
   (``save()``), no el cómputo.
"""
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo

from orm.model_classes import extend_model


def _compute_calendar_id(self):
    """El calendario de la ausencia — ≙ ``_compute_calendar_id``
    (``odoo19c: hr/models/resource_calendar_leaves.py:14-33``).

    Si el recurso pertenece a un empleado con versión vigente y la ausencia
    cae dentro del periodo del contrato, el calendario es el de la versión;
    si no, el del recurso (el inline del ``save()`` del addon padre).
    """
    def date_to_datetime(day, tzinfo):
        # ≙ ``date2datetime`` (``:16-18``): la medianoche local del día,
        # convertida a UTC naíf — la forma en que este árbol guarda
        # ``date_from`` cuando opera en UTC.
        naive = datetime.fromordinal(day.toordinal())
        return naive.replace(tzinfo=tzinfo).astimezone(
            dt_timezone.utc,
        ).replace(tzinfo=None)

    version = None
    if self.resource_id:
        employee = self.resource.hr_hremployee_resource_mixin_set.first()
        version = employee.version if employee and employee.version_id else None

    if version is not None and version.date_start:
        tzinfo = ZoneInfo(
            (version.resource_calendar.tz
             if version.resource_calendar_id else None) or 'UTC',
        )
        start_dt = date_to_datetime(version.date_start, tzinfo)
        end_dt = (date_to_datetime(version.date_end, tzinfo)
                  if version.date_end else datetime.max)
        leave_from = self.date_from
        if leave_from is not None and leave_from.tzinfo is not None:
            # El corte de la referencia opera en UTC naíf; se normaliza el
            # extremo aware antes de comparar.
            leave_from = leave_from.astimezone(dt_timezone.utc).replace(tzinfo=None)
        if leave_from is not None and start_dt <= leave_from < end_dt:
            self.calendar = version.resource_calendar
            return self.calendar

    # ≙ ``super()._compute_calendar_id()`` — el inline del ``save()`` padre:
    # el calendario sigue al del recurso.
    if self.resource_id and not self.calendar_id:
        self.calendar = self.resource.calendar
    return self.calendar if self.calendar_id else None


def apply_hr_resource_calendar_leaves_extensions():
    """Cuelga sobre ``resource.calendar.leaves`` lo que ``hr`` le añade — ≙
    ``_inherit``."""
    extend_model('resource', 'ResourceCalendarLeaves', metodos={
        '_compute_calendar_id': _compute_calendar_id,
    })
