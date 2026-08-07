"""Ganchos de numeración de ``AccountMove`` — la mitad de
``account_move.py`` de la referencia que necesita encadenar comportamiento
YA existente, no sólo agregarlo.

Por qué este archivo está separado de ``account_move.py``
=============================================================

``AccountMoveDebitNote`` (modelo propio, dato nuevo) y estos dos ganchos
(comportamiento que **extiende** un método concreto ya escrito en
``account/models/account_move.py``) tienen necesidades de import opuestas:

- El modelo necesita import normal (``models/__init__.py``), porque Django
  sólo detecta modelos para migraciones si su módulo se importa en la fase
  de carga de apps.
- Estos ganchos necesitan **capturar** ``AccountMove.get_starting_sequence``
  y ``AccountMove.get_last_sequence_domain`` — los objetos función
  concretos ya definidos en ``account`` — para poder llamarlos desde la
  versión extendida. Import normal desde ``models/__init__.py`` funcionaría
  en la práctica (``account`` se carga antes por dependencia), pero el
  patrón que este árbol ya usa para "colgar algo de un modelo ajeno"
  (``account/models/res_company.py``, ``l10n_mx/models/*.py``,
  ``account_qr_code_sepa/models/res_bank.py``) es **siempre** diferir a
  ``AppConfig.ready()`` — es el único punto donde el registro de apps está
  garantizado completo sin depender del orden de ``INSTALLED_APPS``. Se seguía
  aquí; mezclar los dos en un solo archivo forzaría el modelo también a
  ``ready()``, y eso sí rompería las migraciones (Django no lo detectaría).

Los ganchos: ``setattr(Modelo, nombre, funcion) if not hasattr(...)`` NO
alcanza aquí
=================================================================================

Los precedentes citados arriba cuelgan métodos que **no existen** en el
modelo ajeno (``if not hasattr(Modelo, nombre): setattr(...)`` — un
registro "el primero que llega gana", nunca pisa nada). Aquí es distinto:
``get_starting_sequence`` y ``get_last_sequence_domain`` **ya están
definidos** en ``AccountMove`` (``account/models/account_move.py:173,196``)
con lógica real (prefijo por diario+año+tipo; ventana de fechas del
periodo). La referencia los extiende con ``super()`` — el mecanismo
correcto aquí es capturar la función original como variable de módulo
(ejecutado UNA sola vez, la primera vez que Python importa este módulo —
``sys.modules`` lo cachea, así que una segunda llamada a
``apply_account_debit_note_extensions()`` no re-captura ni re-envuelve) y
que la versión nueva la invoque explícitamente — el equivalente funcional
de ``super()`` cuando no hay MRO de por medio.

Qué extienden (fiel a la referencia, símbolo por símbolo)
==============================================================

``get_starting_sequence`` — ≙ ``_get_starting_sequence``
(``odoo19c: account_debit_note/models/account_move.py:29-37``): si el
diario tiene secuencia dedicada de nota de débito, la nota de débito ES una
nota de débito (tiene origen) y el tipo es factura (no nota de crédito), el
nombre base lleva el prefijo ``D``.

``get_last_sequence_domain`` — ≙ ``_get_last_sequence_domain``
(``:39-43``): si el diario tiene secuencia dedicada, la serie se separa
entre "es nota de débito" / "no lo es" — sin este filtro, ambas series
comparten el mismo ``MAX`` y una nota de débito heredaría el consecutivo de
las facturas normales del mismo diario/año.
"""
from addons.account.models import AccountMove
from addons.account_debit_note.models.account_journal import JournalDebitSequence
from addons.account_debit_note.models.account_move import AccountMoveDebitNote

#: Tipos de asiento a los que la referencia aplica el prefijo "D" — ≙
#: ``move_type in ("in_invoice", "out_invoice")``
#: (``odoo19c: account_debit_note/models/account_move.py:34``).
_DEBIT_PREFIX_MOVE_TYPES = ('in_invoice', 'out_invoice')

#: Comportamiento original, capturado una única vez al importar este módulo
#: (ver el docstring de arriba — es el equivalente funcional de ``super()``).
_base_get_starting_sequence = AccountMove.get_starting_sequence
_base_get_last_sequence_domain = AccountMove.get_last_sequence_domain


def get_starting_sequence(self):
    """Nombre base con prefijo ``D`` si aplica — ≙ ``_get_starting_sequence``."""
    base = _base_get_starting_sequence(self)
    if self.move_type not in _DEBIT_PREFIX_MOVE_TYPES:
        return base
    if not JournalDebitSequence.wants_debit_sequence(self.journal):
        return base
    if AccountMoveDebitNote.origin_for(self) is None:
        return base
    return f'D{base}'


def get_last_sequence_domain(self, queryset, relaxed=False):
    """Separa la serie de notas de débito de la de facturas normales — ≙
    ``_get_last_sequence_domain``."""
    queryset = _base_get_last_sequence_domain(self, queryset, relaxed=relaxed)
    if not JournalDebitSequence.wants_debit_sequence(self.journal):
        return queryset
    is_debit_note = AccountMoveDebitNote.origin_for(self) is not None
    if is_debit_note:
        return queryset.filter(debit_note_link__isnull=False)
    return queryset.filter(debit_note_link__isnull=True)


def apply_account_debit_note_extensions():
    """≙ ``_inherit = 'account.move'`` de ``account_debit_note`` (los dos
    ganchos de numeración). Se llama desde ``AccountDebitNoteConfig.ready()``.
    """
    AccountMove.get_starting_sequence = get_starting_sequence
    AccountMove.get_last_sequence_domain = get_last_sequence_domain
