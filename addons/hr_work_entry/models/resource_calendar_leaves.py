"""Extensión de ``resource.calendar.leaves`` — el tipo de entrada de trabajo
de cada ausencia.

Adaptación de Odoo hr_work_entry/models/resource_calendar_leaves.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 16 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03).

``_inherit`` lo expresa ``extend_model`` (criterio de
``hr/models/resource_calendar_leaves.py``); par de Django porque el destino
no declara ``_name``.

Porte símbolo por símbolo — 1 campo + 1 método
===============================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``work_entry_type_id`` (``:9-11``) → ``work_entry_type``
     - portado vía ``campos=`` — su ``groups=hr.group_hr_user`` es ACL del
       cliente Odoo, no se porta (mismo criterio que ``hr_version.py`` D-1)
   * - ``_copy_leave_vals`` (``:13-16``)
     - portado — encadenado sobre ``copy_vals`` (el árbol ya despromovió
       ``_copy_leave_vals`` → ``copy_vals``, ver ``resource:
       models/resource_calendar_leaves.py``) con ``combine=`` que funde el
       dict previo con ``{'work_entry_type_id': …}``
"""
import fields
import models

from orm.method_chain import chain_method
from orm.model_classes import extend_model


def copy_vals(self):
    """≙ ``_copy_leave_vals`` (``odoo19c:
    hr_work_entry/models/resource_calendar_leaves.py:13-16``), mitad nueva
    de la cadena — aporta la clave de este addon; el ``combine`` la funde
    con el dict de la implementación previa (≙ ``res = super()...;
    res['work_entry_type_id'] = …``)."""
    return {'work_entry_type_id': self.work_entry_type_id}


def _merge_copy_vals(new_vals, previous_vals):
    """``combine=`` de la cadena de ``copy_vals`` — funde ambos dicts."""
    merged = dict(previous_vals or {})
    merged.update(new_vals or {})
    return merged


def _wire_copy_vals(model):
    chain_method(model, 'copy_vals', copy_vals, combine=_merge_copy_vals)


def apply_hr_work_entry_resource_calendar_leaves_extensions():
    """Cuelga sobre ``resource.calendar.leaves`` lo que ``hr_work_entry`` le
    añade — ≙ ``_inherit``."""
    extend_model(
        'resource', 'ResourceCalendarLeaves',
        campos={
            'work_entry_type': fields.Many2one(
                'hr_work_entry.HrWorkEntryType', on_delete=models.SET_NULL,
                verbose_name='Work Entry Type', null=True, blank=True,
                related_name='calendar_leaves',
                help_text='Odoo work_entry_type_id (groups=hr.group_hr_user '
                          '— ACL del cliente, no se porta).',
            ),
        },
        luego=_wire_copy_vals,
    )
