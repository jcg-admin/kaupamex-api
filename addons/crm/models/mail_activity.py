"""``mail.activity`` — lo que ``crm`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/crm/models/mail_activity.py`` (LGPL-3, 26
líneas) — atribución y aviso de licencia preservados (DEC-KX-03).

Porte BLOQUEADO por ``calendar`` — 0 de 1 símbolo
=================================================

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Símbolo (línea)
     - Estado
   * - ``action_create_calendar_event`` (``:9``)
     - BLOQUEADO por ``calendar``

La causa, medida
================

El símbolo **releva de un método que no existe** y **lee un campo que no
existe**, y los dos vienen del addon ``calendar``, ausente de este árbol:

- ``super().action_create_calendar_event()`` — medido: 0 hits de
  ``action_create_calendar_event`` en ``addons/mail/models/``;
- ``self.calendar_event_id.opportunity_id`` — ``calendar_event_id`` lo declara
  ``calendar`` sobre ``mail.activity``, y ``opportunity_id`` es justo el campo
  que ``crm/models/calendar.py`` cuelga y que está bloqueado por lo mismo.

``mail.activity`` **sí existe** aquí (``addons/mail/models/mail_activity.py:32``),
así que el bloqueo es del símbolo, no del modelo: en cuanto ``calendar`` exista,
este archivo se escribe sin tocar nada más.

Lo que la fuente hace, para cuando se desbloquee: al crear la reunión desde una
actividad ligada a una oportunidad, inyecta en el contexto de la acción los
valores por defecto de "agendar reunión" de esa oportunidad —el contacto entra
como asistente— y fija ``initial_date`` a la fecha de inicio del evento.
``CrmLead.action_schedule_meeting`` ya está portado y es quien los aporta.

Sucesor: tarea **#160**.
"""


def apply_crm_extensions():
    """No-op declarado — ver el docstring del módulo."""
    return None


__all__ = ['apply_crm_extensions']
