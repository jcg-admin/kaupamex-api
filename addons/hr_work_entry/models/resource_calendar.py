"""Extensión de ``resource.calendar`` — los tramos de ausencia no cuentan
como horas de trabajo.

Adaptación de Odoo hr_work_entry/models/resource_calendar.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 15 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03).

``_inherit`` lo expresa ``extend_model`` (criterio de
``hr/models/resource_calendar.py``); par de Django porque el destino no
declara ``_name``.

Porte símbolo por símbolo — 2 de 2
===================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_compute_hours_per_week`` (``:10-12``)
     - resuelto por construcción (D-1) — la fuente sólo re-declara el
       ``@api.depends`` añadiendo ``attendance_ids.work_entry_type_id.
       is_leave``; aquí ``hours_per_week`` es una ``property`` que recalcula
       en CADA lectura desde ``_global_attendances()``, así que el disparo
       extra no tiene nada que disparar: la dependencia ya está cubierta
   * - ``_get_global_attendances`` (``:14-15``)
     - portado — encadenado sobre ``_global_attendances`` (D-2) con
       ``combine=``: filtra de la lista previa los tramos cuyo tipo de
       entrada es ausencia (``work_entry_type_id.is_leave``)

Divergencias declaradas
========================

1. **``_compute_hours_per_week`` no se instala** — no hay ``api.depends``
   que extender; el override de la fuente es SOLO el decorador (su cuerpo es
   ``super()._compute_hours_per_week()``). Con la property que recalcula
   siempre, instalar un método vacío sería un stub sin efecto.
2. **``_get_global_attendances`` → cadena sobre ``_global_attendances``** —
   el addon ``resource`` de este árbol ya declaró ese método con ese nombre
   (``resource: models/resource_calendar.py::_global_attendances``, "Odoo
   ``_get_global_attendances``"); se encadena el nombre del árbol para que
   TODOS sus consumidores (``hours_per_week``, ``_days_per_week``) reciban
   el filtro, que es exactamente lo que el ``super()`` de la fuente compra.
"""
from orm.method_chain import chain_method
from orm.model_classes import extend_model


def _global_attendances(self):
    """≙ ``_get_global_attendances`` (``odoo19c:
    hr_work_entry/models/resource_calendar.py:14-15``) — mitad nueva de la
    cadena: no aporta tramos propios (``None`` → el ``combine`` recibe la
    lista de la implementación previa y la filtra)."""
    return None


def _drop_leave_attendances(_new_result, previous_attendances):
    """``combine=`` de la cadena — ≙ ``super()._get_global_attendances()
    .filtered(lambda a: not a.work_entry_type_id.is_leave)`` (``:15``)."""
    return [
        attendance for attendance in (previous_attendances or [])
        if not (
            attendance.work_entry_type_id
            and attendance.work_entry_type.is_leave
        )
    ]


def _wire_global_attendances(model):
    chain_method(
        model, '_global_attendances', _global_attendances,
        combine=_drop_leave_attendances,
    )


def apply_hr_work_entry_resource_calendar_extensions():
    """Cuelga sobre ``resource.calendar`` lo que ``hr_work_entry`` le añade —
    ≙ ``_inherit``."""
    extend_model('resource', 'ResourceCalendar', luego=_wire_global_attendances)
