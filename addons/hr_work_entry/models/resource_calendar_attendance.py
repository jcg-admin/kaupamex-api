"""Extensión de ``resource.calendar.attendance`` — el tipo de entrada de
trabajo de cada tramo del horario.

Adaptación de Odoo hr_work_entry/models/resource_calendar_attendance.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 22 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03).

``_inherit`` lo expresa ``extend_model`` (criterio de
``hr/models/resource_calendar.py``); par de Django porque el destino no
declara ``_name``.

Porte símbolo por símbolo — 1 campo + 3 métodos
================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``work_entry_type_id`` (``:12-14``) → ``work_entry_type``
     - portado vía ``campos=`` — su ``groups=hr.group_hr_user`` es ACL del
       cliente Odoo, no se porta (mismo criterio que ``hr_version.py`` D-1)
   * - ``_default_work_entry_type_id`` (``:9-10``)
     - portado como función de módulo (``default=`` del campo) —
       ``env.ref`` → búsqueda por ``code == 'WORK100'`` (D-1)
   * - ``_copy_attendance_vals`` (``:16-19``)
     - portado — encadenado sobre ``copy_vals`` (D-2) con ``combine=`` que
       funde el dict previo con ``{'work_entry_type_id': …}``
   * - ``_is_work_period`` (``:21-22``)
     - portado — envolviendo la ``property`` ``is_work_period`` del árbol
       (D-3): un tramo cuyo tipo es ausencia NO es periodo de trabajo

Divergencias declaradas
========================

1. **``env.ref('hr_work_entry.work_entry_type_attendance')`` → ``code ==
   'WORK100'``** — los XML ids de ``data/`` no se cargan aquí.
2. **``_copy_attendance_vals`` → cadena sobre ``copy_vals``** — el addon
   ``resource`` ya despromovió ese símbolo a ``copy_vals`` ("Odoo
   ``_copy_attendance_vals``"); se encadena el nombre del árbol para que sus
   consumidores existentes reciban la clave nueva.
3. **``_is_work_period`` → envoltura de la ``property``** — el árbol lo
   declara ``property is_work_period`` ("Odoo ``_is_work_period``");
   ``chain_method`` rechaza properties (falla ruidoso a propósito), así que
   la extensión REEMPLAZA la property por otra que compone: ``not
   work_entry_type.is_leave and <previa>`` — el ``super()`` de ``:22``.
"""
import fields
import models

from addons.hr_work_entry.models.hr_work_entry_type import (
    ATTENDANCE_TYPE_CODE,
    HrWorkEntryType,
)
from orm.method_chain import chain_method
from orm.model_classes import extend_model


def _default_work_entry_type_id():
    """≙ ``_default_work_entry_type_id`` (``odoo19c:
    hr_work_entry/models/resource_calendar_attendance.py:9-10``) — D-1;
    función nombrada de módulo (serializable en migraciones)."""
    return (
        HrWorkEntryType.objects.filter(code=ATTENDANCE_TYPE_CODE)
        .values_list('pk', flat=True).first()
    )


def copy_vals(self):
    """≙ ``_copy_attendance_vals`` (``:16-19``), mitad nueva de la cadena —
    aporta la clave de este addon; el ``combine`` la funde con el dict de la
    implementación previa (≙ ``res = super()...; res[...] = ...``)."""
    return {'work_entry_type_id': self.work_entry_type_id}


def _merge_copy_vals(new_vals, previous_vals):
    """``combine=`` de la cadena de ``copy_vals`` — funde ambos dicts (la
    clave nueva gana, como el ``res['work_entry_type_id'] = …`` de la
    fuente)."""
    merged = dict(previous_vals or {})
    merged.update(new_vals or {})
    return merged


def _wire_copy_vals_and_is_work_period(model):
    chain_method(model, 'copy_vals', copy_vals, combine=_merge_copy_vals)
    # _is_work_period (:21-22) — D-3: componer la property del árbol.
    previous_is_work_period = model.is_work_period.fget
    if getattr(previous_is_work_period, '_hr_work_entry_wrapped', False):
        # ready() puede correr más de una vez (autoreloader) — misma guarda
        # de idempotencia que _already_in_chain de chain_method.
        return

    def is_work_period(self):
        """≙ ``_is_work_period`` (``:21-22``) — ``not
        work_entry_type_id.is_leave and super()._is_work_period()``."""
        is_leave = bool(
            self.work_entry_type_id and self.work_entry_type.is_leave
        )
        return not is_leave and previous_is_work_period(self)

    is_work_period._hr_work_entry_wrapped = True
    model.is_work_period = property(is_work_period)


def apply_hr_work_entry_resource_calendar_attendance_extensions():
    """Cuelga sobre ``resource.calendar.attendance`` lo que ``hr_work_entry``
    le añade — ≙ ``_inherit``."""
    extend_model(
        'resource', 'ResourceCalendarAttendance',
        campos={
            'work_entry_type': fields.Many2one(
                'hr_work_entry.HrWorkEntryType', on_delete=models.SET_NULL,
                verbose_name='Work Entry Type', null=True, blank=True,
                related_name='calendar_attendances',
                default=_default_work_entry_type_id,
                help_text='Odoo work_entry_type_id (groups=hr.group_hr_user '
                          '— ACL del cliente, no se porta).',
            ),
        },
        luego=_wire_copy_vals_and_is_work_period,
    )
