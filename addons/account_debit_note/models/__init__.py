"""Modelos del addon ``account_debit_note`` — un archivo por modelo de la
referencia, más ``account_move_sequence.py`` (ver su docstring para por qué).

``account_move_sequence.py`` **deliberadamente no se importa aquí**: cuelga
comportamiento de ``account.AccountMove`` que ya existe, y ese import se
difiere a ``AccountDebitNoteConfig.ready()`` — importarlo aquí no rompería
nada hoy (``account`` se carga antes por dependencia), pero se aparta del
patrón que el resto del árbol usa para "colgar algo de un modelo ajeno"
(ver el docstring de ese archivo).
"""
from .account_journal import JournalDebitSequence
from .account_move import AccountMoveDebitNote

__all__ = [
    'JournalDebitSequence',
    'AccountMoveDebitNote',
]
