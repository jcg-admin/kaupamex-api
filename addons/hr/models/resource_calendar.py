"""Extensión de ``resource.calendar`` — traspaso de ausencias (Odoo ``hr``).

Adaptación de Odoo hr/models/resource_calendar.py (odoo-tools@622ddc2a,
odoo19c:, LGPL-3, 25 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03).

Porte símbolo por símbolo — 1 de 1
===================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
     - Forma aquí
   * - ``transfer_leaves_to`` (``:9-24``)
     - portado
     - ``extend_model('resource', 'ResourceCalendar', metodos=…)``; nombre
       **verbatim**

``_inherit`` no es un símbolo a portar: lo expresa ``extend_model`` (mismo
criterio que ``stock/models/res_users.py``). El destino se nombra con el par
de Django porque ``resource.ResourceCalendar`` no declara ``_name`` (misma
divergencia D-3 de aquel archivo).

Divergencias declaradas
========================

1. **El dominio Odoo se traduce a un queryset.** La referencia arma un
   dominio (``calendar_id in self.ids``, ``date_from >= from_date``, y
   ``resource_id in resources.ids`` si aplica) y hace un ``write`` masivo;
   aquí es el mismo corte con ``filter(...).update(...)`` — un solo UPDATE,
   igual que el ``write`` de la referencia.
2. **``fields.Datetime.now()`` (naíf UTC) → ``django.utils.timezone.now()``**
   (aware) — es el reloj canónico de este árbol; el truncado a medianoche se
   conserva verbatim (``replace(hour=0, minute=0, second=0, microsecond=0)``).
3. **``self`` es una instancia, no un recordset** — el ``in self.ids`` de la
   referencia queda ``calendar=self``; quien necesite traspasar desde varios
   calendarios itera, igual que el resto de los métodos de instancia de este
   árbol.
"""
from django.utils import timezone

from addons.resource.models.resource_calendar_leaves import ResourceCalendarLeaves
from orm.model_classes import extend_model


def transfer_leaves_to(self, other_calendar, resources=None, from_date=None):
    """Traspasa ausencias de este calendario a ``other_calendar`` — ≙
    ``transfer_leaves_to`` (``odoo19c: hr/models/resource_calendar.py:9-24``).

    Se traspasan las ``resource.calendar.leaves`` ligadas a ``resources``
    (o todas si es ``None``) que empiecen después de ``from_date`` (hoy a
    medianoche si es ``None``).
    """
    from_date = from_date or timezone.now().replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    leaves = ResourceCalendarLeaves.objects.filter(
        calendar=self, date_from__gte=from_date,
    )
    if resources is not None:
        leaves = leaves.filter(resource__in=list(resources))
    return leaves.update(calendar=other_calendar)


def apply_hr_resource_calendar_extensions():
    """Cuelga sobre ``resource.calendar`` lo que ``hr`` le añade — ≙ ``_inherit``."""
    extend_model('resource', 'ResourceCalendar', metodos={
        'transfer_leaves_to': transfer_leaves_to,
    })
