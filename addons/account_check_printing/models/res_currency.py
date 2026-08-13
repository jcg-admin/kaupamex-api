"""``res.currency`` — lo que ``account_check_printing`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/account_check_printing/models/
account_payment.py`` (``odoo-tools@622ddc2a``, LGPL-3 — atribución y aviso de
licencia preservados, DEC-KX-03) — la referencia consume
``self.currency_id.amount_to_text(self.amount)`` (``:102``, para
``check_amount_in_words``) y espera que ese método viva en la clase base de
``res.currency``.

Primer consumidor real de un método declarado NO portado
==============================================================

``base/models/res_currency.py`` declara ``amount_to_text`` explícitamente
NO portado: *"presentación (formato de importe, monto en palabras) — sin
consumidor de UI en este core de backend"* (medido:
``grep -n "amount_to_text" base/models/res_currency.py`` → **0 hits** de
definición, sólo la mención en la lista de lo no portado [PROVEN]).
``account_check_printing`` es su primer consumidor real — no se puede
declarar NO PORTADO otra vez sin violar ``porte-completo-no-parcial.md``
("si el ORM no tiene un mecanismo, se construye"). Se construye AQUÍ y se
cuelga vía ``chain_method`` desde ``AppConfig.ready()`` — nunca existió
antes, así que la instalación es directa (ver ``orm/method_chain.py``), y no
se toca ``base/models/res_currency.py``.

Divergencia declarada — español, no inglés; "PESOS", no el nombre de la
moneda
=====================================================================================

Sin ``num2words`` en el lockfile (medido: ``grep -n "num2words" uv.lock`` →
**0 hits** [PROVEN]) y sin autorización para tocar ``pyproject.toml`` (fuera
de ``account_check_printing/``), el conversor de número a letras se
construye aquí, en español — este producto es un e-commerce mexicano
(Kaupamex/PracticaYoruba), y el formato que un talonario mexicano espera es
``"<MONTO EN LETRA> PESOS NN/100 M.N."``, no el inglés
``"One hundred Dollars and Fifty Cents"`` de la referencia. Misma
capacidad (montos infalsificables en el talón, cifra y letra coinciden),
forma localizada — no se lee el nombre/símbolo de ``self`` (la moneda): se
usa siempre "PESOS", que es lo que un talonario mexicano espera imprimir
sea cual sea la moneda registrada en el pago. Construir la tabla de nombres
de moneda en plural español es trabajo de ``base``, no de este addon.

El conversor cubre 0 a 999 999 999 (unidades, miles, millones) — más que
suficiente para un importe de cheque; fuera de ese rango degrada al
numeral en dígitos en vez de fallar en silencio. No aplica la apócope
gramatical de "veintiuno"→"veintiún" ante sustantivo — simplificación
declarada, sin consumidor que la exija hoy.
"""
from decimal import ROUND_HALF_UP, Decimal

from orm.method_chain import chain_method
from addons.base.models import ResCurrency

#: ≙ las unidades 0-9, con la forma apocopada "un" (no "uno") — es la que
#: usa un talonario ("un peso", no "uno peso").
_UNITS = ('', 'un', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve')
_TEENS = (
    'diez', 'once', 'doce', 'trece', 'catorce', 'quince', 'dieciséis',
    'diecisiete', 'dieciocho', 'diecinueve',
)
_TWENTIES = (
    'veinte', 'veintiuno', 'veintidós', 'veintitrés', 'veinticuatro',
    'veinticinco', 'veintiséis', 'veintisiete', 'veintiocho', 'veintinueve',
)
_TENS = (
    '', '', 'veinte', 'treinta', 'cuarenta', 'cincuenta', 'sesenta',
    'setenta', 'ochenta', 'noventa',
)
_HUNDREDS = (
    '', 'ciento', 'doscientos', 'trescientos', 'cuatrocientos',
    'quinientos', 'seiscientos', 'setecientos', 'ochocientos', 'novecientos',
)

#: Techo del conversor — ver la divergencia declarada arriba.
_MAX_CONVERTIBLE = 999_999_999


def _under_100(n):
    if n < 10:
        return _UNITS[n]
    if n < 20:
        return _TEENS[n - 10]
    if n < 30:
        return _TWENTIES[n - 20]
    tens, unit = divmod(n, 10)
    if unit == 0:
        return _TENS[tens]
    return f'{_TENS[tens]} y {_UNITS[unit]}'


def _under_1000(n):
    if n == 0:
        return ''
    if n == 100:
        return 'cien'
    hundreds, rest = divmod(n, 100)
    words = _HUNDREDS[hundreds]
    if rest:
        words = f'{words} {_under_100(rest)}'.strip()
    return words


def integer_to_words(n):
    """El entero ``n`` (0 <= n <= 999 999 999) en palabras, en español.

    Fuera del rango cubierto, degrada al numeral en dígitos — declarado
    explícitamente arriba, no un silencio (``check_silent_oks``).
    """
    n = int(n)
    if n < 0 or n > _MAX_CONVERTIBLE:
        return str(n)
    if n == 0:
        return 'cero'

    millions, resto = divmod(n, 1_000_000)
    thousands, units = divmod(resto, 1_000)

    partes = []
    if millions:
        partes.append('un millón' if millions == 1 else f'{_under_1000(millions)} millones')
    if thousands:
        partes.append('mil' if thousands == 1 else f'{_under_1000(thousands)} mil')
    if units:
        partes.append(_under_1000(units))
    return ' '.join(p for p in partes if p)


def amount_to_text(self, amount):
    """``<monto en letra> PESOS NN/100 M.N.`` — ≙ Odoo ``amount_to_text``.

    ``self`` es la instancia de ``res.currency`` (por fidelidad a la firma
    de la referencia, que la consulta por ``related='journal_id.currency'``);
    no se usa su nombre — ver la divergencia declarada del módulo.
    """
    amount = Decimal(amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    integer_part = int(amount)
    cents = int((amount - integer_part) * 100)
    words = integer_to_words(integer_part).upper()
    return f'{words} PESOS {cents:02d}/100 M.N.'


def apply_account_check_printing_currency_extensions():
    """≙ la mitad de ``_inherit = 'res.currency'`` que este addon necesita.

    Se llama desde ``AccountCheckPrintingConfig.ready()``.
    """
    chain_method(ResCurrency, 'amount_to_text', amount_to_text)
