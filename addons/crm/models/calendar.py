"""``calendar.event`` — lo que ``crm`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/crm/models/calendar.py`` (LGPL-3, 54 líneas)
— atribución y aviso de licencia preservados (DEC-KX-03).

Porte BLOQUEADO por ``calendar`` — 0 de 5 símbolos
==================================================

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Símbolo (línea)
     - Estado
   * - ``default_get`` (``:9``)
     - BLOQUEADO por ``calendar``
   * - ``opportunity_id`` (campo, ``:26``)
     - BLOQUEADO por ``calendar``
   * - ``_compute_is_highlighted`` (``:30``)
     - BLOQUEADO por ``calendar`` — releva de un método del addon ausente
   * - ``create`` (``:37``)
     - BLOQUEADO por ``calendar``
   * - ``_is_crm_lead`` (``:44``)
     - BLOQUEADO por ``calendar`` — su única razón de existir es servir a
       ``default_get``, y sin el modelo destino no hay dónde colgarlo

La causa, medida
================

El addon ``calendar`` **no existe en este árbol**: ``ls addons/`` no lo
lista, y ``calendar.event`` no está en el registro. Los cinco símbolos
extienden ese modelo, así que ninguno tiene destino.

No es un porte parcial ni una divergencia de mecanismo: es una **arista
dirigida a un addon ausente**, que es el segundo desenlace válido de
``porte-completo-no-parcial.md`` (bloqueo medido con sucesor registrado).

Lo que este bloqueo arrastra
============================

``crm/models/mail_activity.py`` cae por lo mismo: su único símbolo llama a
``action_create_calendar_event`` y lee ``calendar_event_id``, los dos del addon
ausente.

Y en ``crm_lead.py``, ``log_meeting`` —el consumidor de ``create`` de arriba—
ya está portado y esperando: en cuanto ``calendar`` exista, este archivo se
escribe contra un destino que ya sabe recibirlo.

Sucesor: tarea **#160**.
"""


def apply_crm_extensions():
    """No-op declarado — ver el docstring del módulo."""
    return None


__all__ = ['apply_crm_extensions']
