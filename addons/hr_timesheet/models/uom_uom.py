"""``uom.uom`` — widget de captura de la hoja de horas (Odoo
``hr_timesheet``).

Adaptación de Odoo ``hr_timesheet/models/uom_uom.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 20 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST: 1 clase (``_inherit``), 1 campo, 1 método.

===================================  ====================================
Símbolo (línea)                      Desenlace
===================================  ====================================
``timesheet_widget`` (:18-19)        **portado** — columna real
                                      (``CharField``).
``_unprotected_uom_xml_ids`` (:9-17) **BLOQUEADO** — protege de borrado dos
                                      UOM por su xmlid (``product_uom_dozen``,
                                      ``product_uom_pack_6``); depende de un
                                      mecanismo de identificadores externos
                                      (``ir.model.data``) sobre ``uom.Uom``
                                      no verificado en este pase, y de un
                                      guard de borrado (``unlink``) que
                                      tampoco existe hoy sobre este modelo.
===================================  ====================================
"""
import fields

from addons.uom.models import Uom


def _add_if_absent(model, name, field):
    """Idéntico al de ``models/hr_timesheet.py`` de este mismo addon."""
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


def apply_hr_timesheet_uom_uom_extensions():
    """Cuelga ``timesheet_widget`` sobre ``uom.Uom``.

    La llama ``HrTimesheetConfig.ready()``.
    """
    _add_if_absent(Uom, 'timesheet_widget', fields.Char(
        max_length=255, blank=True, default='',
        help_text='Odoo timesheet_widget. Widget del cliente web usado '
                  'cuando esta unidad captura la hoja de horas.',
    ))
