r"""Paquete ``tools`` de ``account_edi_ubl_cii`` — plantillas de orden de nodos UBL.

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/tools/__init__.py``
(``odoo-tools@622ddc2a``, LGPL-3, 10 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

**Porte verbatim: 9 de 9 sentencias de importación.** El paquete no declara
símbolos propios: reexporta los cuatro documentos raíz (``Invoice``,
``CreditNote``, ``DebitNote``, ``Order``) para que los modelos los importen
con ``from .. tools import Invoice, CreditNote, DebitNote``, tal cual hace la
fuente.

``ubl_20_optional_fields`` y ``ubl_21_extensions`` NO se importan aquí — fiel
a la fuente, que los deja para importación directa por ruta completa.
"""
from . import ubl_21_common
from . import ubl_21_invoice
from . import ubl_21_credit_note
from . import ubl_21_debit_note
from . import ubl_21_order

from .ubl_21_invoice import Invoice
from .ubl_21_credit_note import CreditNote
from .ubl_21_debit_note import DebitNote
from .ubl_21_order import Order

__all__ = [
    'ubl_21_common', 'ubl_21_invoice', 'ubl_21_credit_note',
    'ubl_21_debit_note', 'ubl_21_order',
    'Invoice', 'CreditNote', 'DebitNote', 'Order',
]
