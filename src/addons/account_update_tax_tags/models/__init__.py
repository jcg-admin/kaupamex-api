"""Modelos del addon ``account_update_tax_tags`` — puentes hacia ``account.move.line``.

Ninguno existe en la referencia (``odoo19c: addons/account_update_tax_tags/``
no trae ``models/`` — sólo ``wizard/``): son la infraestructura que este
puerto construye porque los tres campos que el wizard necesita
(``tax_ids``, ``tax_repartition_line_id``, ``tax_tag_ids``) no están
portados en ``account.move.line`` y este pase no puede tocar ``account/``.
Ver el docstring de ``account_move_line_tax_link.py`` para la medición y la
divergencia declarada.

Importados eagerly (a diferencia de un ``ready()`` con ``importlib``,
excepción #4 de ``no-lazy-imports.md``): estos modelos son NUEVOS —no
cuelgan comportamiento sobre una clase ajena que deba existir primero—, así
que no hay riesgo de ``AppRegistryNotReady``. Mismo criterio que
``addons/account_debit_note/models/__init__.py`` para
``AccountMoveDebitNote``/``JournalDebitSequence``, que también declaran FK
por *string* hacia modelos de otro app sin necesitar ``ready()``.
"""
from .account_move_line_tax_link import (
    AccountMoveLineTag,
    AccountMoveLineTax,
    AccountMoveLineTaxRepartition,
)

__all__ = [
    'AccountMoveLineTag',
    'AccountMoveLineTax',
    'AccountMoveLineTaxRepartition',
]
