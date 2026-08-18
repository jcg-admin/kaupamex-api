"""Asistentes de ``base`` — ``odoo19c: odoo/addons/base/wizard/``.

En la referencia un asistente es un ``TransientModel``: un modelo persistente
temporal cuyo estado (las casillas del formulario) vive en una fila que un
vacuum recolecta. Aquí no hay formulario que rellenar, así que se sigue el
precedente ya fijado por ``account_check_printing.print_prenumbered_checks``
y ``account_debit_note``: **"formulario, no tabla"** — el asistente es una
clase con ``classmethod``, y lo que allá eran campos del wizard son aquí
parámetros de la llamada.
"""
from addons.base.wizard.base_partner_merge import MergeGroup, PartnerMerge
from addons.base.wizard.wizard_ir_model_menu_create import ModelMenuCreate

__all__ = ['MergeGroup', 'PartnerMerge', 'ModelMenuCreate']
