"""``ir.sequence`` — lo que ``account_check_printing`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/account_check_printing/models/
account_journal.py`` (líneas 53, 76-77) y ``account_payment.py``
(línea 111, 159) (``odoo-tools@622ddc2a``, LGPL-3 — atribución y aviso de
licencia preservados, DEC-KX-03). La referencia no tiene un
``ir_sequence.py`` propio — el consumo de
``sequence.get_next_char(sequence.number_next_actual)`` viene de esos dos
archivos. Se documenta aquí porque es lo que este puerto le AÑADE a
``base.IrSequence`` para poder portarlos.

``get_next_char`` — leer sin consumir
==========================================

``base.IrSequence.get_next()`` (``base/models/ir_sequence.py:90-103``)
SIEMPRE incrementa ``number_next`` al leer — es el equivalente de la
referencia ``_next()``/``next_by_id()``. La referencia necesita además una
lectura que **no** consuma:
``sequence.get_next_char(sequence.number_next_actual)``
(``odoo19c: account_journal.py:53``, para mostrar "el próximo número" sin
gastarlo). Esa mitad no existía (``grep -n "get_next_char"
base/models/ir_sequence.py`` → **0 hits** [PROVEN]) — se construye aquí y se
cuelga con ``chain_method`` (nunca existió antes, así que el resultado es
una instalación directa, ver ``orm/method_chain.py``).

Divergencia declarada — ``number_next_actual`` no es una columna aparte
===========================================================================

La referencia distingue ``number_next`` (el valor editable del formulario)
de ``number_next_actual`` (el valor EFECTIVO, que con ``use_date_range``
puede vivir en una subsecuencia por rango de fecha). Nuestro ``IrSequence``
no implementa subsecuencias por rango — ``use_date_range`` es un campo
declarado sin lógica propia (``grep -n "date_range"
base/models/ir_sequence.py`` → sólo la línea de declaración del campo, la
clase entera no tiene ningún otro método que la lea [PROVEN]) — así que
aquí no hay diferencia entre "lo declarado" y "lo efectivo": este puerto usa
``number_next`` en todos los puntos donde la referencia lee/escribe
``number_next_actual`` (ver ``models/account_journal.py``).
"""
from orm.method_chain import chain_method
from addons.base.models import IrSequence


def get_next_char(self, number):
    """Formatea ``number`` con el prefijo/sufijo/padding de esta secuencia,
    SIN consumir un valor — ≙ Odoo ``get_next_char``.

    Reutiliza los mismos helpers que ``get_next()`` (``_interpolation_dict``/
    ``_interpolate``) para que el formato producido sea IDÉNTICO al que
    ``get_next()`` habría dado si se hubiera llamado — es la garantía que
    hace que "peek" y "consumir" nunca diverjan en forma.
    """
    tokens = self._interpolation_dict()
    prefix = self._interpolate(self.prefix, tokens)
    suffix = self._interpolate(self.suffix, tokens)
    return '%s%%0%sd%s' % (prefix, self.padding, suffix) % int(number)


def apply_account_check_printing_ir_sequence_extensions():
    """≙ la mitad de ``_inherit = 'ir.sequence'`` que este addon necesita.

    Se llama desde ``AccountCheckPrintingConfig.ready()``.
    """
    chain_method(IrSequence, 'get_next_char', get_next_char)
