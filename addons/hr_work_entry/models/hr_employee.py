"""Extensión de ``hr.employee`` — entradas de trabajo del empleado.

Adaptación de Odoo hr_work_entry/models/hr_employee.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 59 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03).

``_inherit`` no es un símbolo a portar: lo expresa ``extend_model`` (criterio
de ``hr/models/resource_calendar.py``). El destino se nombra con el par de
Django (``'hr', 'HrEmployee'``).

Porte símbolo por símbolo — 3 campos + 4 métodos
=================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``has_work_entries`` (``:10``) con ``_compute_has_work_entries``
       (``:14-26``)
     - portado como property — el ``EXISTS`` por lote (SQL crudo) queda
       ``self.work_entries.exists()`` por instancia (D-1)
   * - ``work_entry_source`` (``:11``, ``related='version_id.
       work_entry_source'`` ``inherited=True``)
     - portado como property (lee la versión vigente; el ``readonly=False``
       lo escribe quien escriba la versión)
   * - ``work_entry_source_calendar_invalid`` (``:12``, related inherited)
     - portado como property (delega en la property de ``hr.version``)
   * - ``create_version`` (``:28-34``)
     - portado — ``chain_method`` con ``combine=`` (el ``super()`` de este
       idioma): tras crear la versión, resetea ``date_generated_from/to`` a
       la medianoche de hoy
   * - ``action_open_work_entries`` (``:36-49``)
     - BLOQUEADO por ``ir.actions.act_window`` — acción de cliente Odoo,
       misma familia (b)/(c) que ``hr/models/hr_version.py`` ya declaró; la
       capa DRF compone su propia respuesta de navegación
   * - ``generate_work_entries`` (``:51-59``)
     - BLOQUEADO por ``HrVersion.generate_work_entries`` (cadena del motor
       de intervalos — ver ``hr_version.py`` de este addon); este método es
       sólo su despachador (resolver versiones que solapan el periodo, que
       YA existe portado: ``HrEmployee._get_versions_with_contract_overlap_
       with_period``) y se escribe al desbloquearse aquél

Divergencias declaradas
========================

1. **``_compute_has_work_entries``** — la fuente hace un solo SQL con
   ``EXISTS`` para el lote; aquí es ``exists()`` sobre el reverso
   (``work_entries``, el ``related_name`` que este addon declara en
   ``HrWorkEntry.employee``) por instancia — mismo predicado, sin el lote.
2. **``fields.Datetime.now()`` (naíf UTC) → ``django.utils.timezone.now()``**
   (aware) — el reloj canónico del árbol (mismo criterio que
   ``hr/models/resource_calendar.py``); el truncado a medianoche se conserva
   verbatim.
"""
from django.utils import timezone

from orm.method_chain import chain_method
from orm.model_classes import extend_model


def _generation_boundary_today():
    """La medianoche de hoy — el ``fields.Datetime.now().replace(hour=0,
    minute=0, second=0, microsecond=0)`` de la fuente (D-2)."""
    return timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)


def _compute_has_work_entries(self):
    """≙ ``_compute_has_work_entries`` (``odoo19c:
    hr_work_entry/models/hr_employee.py:14-26``) — D-1."""
    if not self.pk:
        return False
    return self.work_entries.exists()


def _work_entry_source(self):
    """≙ ``work_entry_source`` (``related='version_id.work_entry_source'``,
    ``:11``)."""
    return self.version.work_entry_source if self.version_id else None


def _work_entry_source_calendar_invalid(self):
    """≙ ``work_entry_source_calendar_invalid`` (``:12``) — delega en la
    property homónima de ``hr.version``."""
    if not self.version_id:
        return False
    return self.version.work_entry_source_calendar_invalid


def _reset_generation_boundaries(_new_result, new_version):
    """``combine=`` de ``chain_method`` para ``create_version`` — recibe el
    resultado de ambas mitades; la previa (``hr``) devuelve la versión nueva
    y aquí se le resetean las fronteras (≙ ``new_version.update({...})``)."""
    if new_version is not None:
        boundary = _generation_boundary_today()
        new_version.date_generated_from = boundary
        new_version.date_generated_to = boundary
        new_version.save(update_fields=['date_generated_from', 'date_generated_to'])
    return new_version


def _create_version_noop(self, values):
    """≙ ``create_version`` (``:28-34``), mitad nueva de la cadena — no
    aporta valor propio (todo el efecto vive en el ``combine``,
    ``_reset_generation_boundaries``); devuelve ``None`` para que ``combine``
    reciba ``(None, versión_de_la_previa)``."""
    return None


def _wire_create_version(model):
    """Encadena ``create_version`` con ``combine=`` — el ``super()`` de este
    idioma (``chain_method`` corre la mitad nueva, luego la previa, y funde
    con ``_reset_generation_boundaries``)."""
    chain_method(
        model, 'create_version', _create_version_noop,
        combine=_reset_generation_boundaries,
    )


def apply_hr_work_entry_hr_employee_extensions():
    """Cuelga sobre ``hr.employee`` lo que ``hr_work_entry`` le añade — ≙
    ``_inherit``."""
    extend_model(
        'hr', 'HrEmployee',
        propiedades={
            'has_work_entries': _compute_has_work_entries,
            'work_entry_source': _work_entry_source,
            'work_entry_source_calendar_invalid': _work_entry_source_calendar_invalid,
        },
        luego=_wire_create_version,
    )
