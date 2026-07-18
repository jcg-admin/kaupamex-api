"""Modelos del addon ``account`` — paquete espejo de ``odoo/addons/account/models/``.

Un archivo por modelo (monolito modular, como Odoo). Núcleo del libro mayor de
doble entrada:

- ``account_account.py``    → ``AccountAccount``   (plan de cuentas).
- ``account_journal.py``    → ``AccountJournal``   (diarios).
- ``account_tax.py``        → ``AccountTax``       (impuestos).
- ``account_move.py``       → ``AccountMove``      (asientos / facturas).
- ``account_move_line.py``  → ``AccountMoveLine``  (apuntes).
- ``account_payment.py``    → ``AccountPayment``   (pagos).
"""
from .account_account import AccountAccount
from .account_journal import AccountJournal
from .account_move import AccountMove
from .account_move_line import AccountMoveLine
from .account_payment import AccountPayment
from .account_tax import AccountTax

__all__ = [
    'AccountAccount',
    'AccountJournal',
    'AccountTax',
    'AccountMove',
    'AccountMoveLine',
    'AccountPayment',
]
