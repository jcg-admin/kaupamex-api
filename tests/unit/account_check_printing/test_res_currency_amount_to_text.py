"""Contrato del conversor de número a letras — ≙ Odoo ``res.currency.
amount_to_text``, colgado por ``account_check_printing`` sobre
``base.ResCurrency`` (ver ``models/res_currency.py``).

``chain_method`` opera sobre la clase Python, no sobre una tabla — no
requiere ``addons.account_check_printing`` en ``INSTALLED_APPS`` para el
conversor en sí. Se aplica explícitamente una vez, igual que
``tests/unit/account_debit_note/test_account_move_sequence_debit_note.py``
hace con ``apply_account_debit_note_extensions()``.
"""
from decimal import Decimal

from addons.account_check_printing.models.res_currency import (
    apply_account_check_printing_currency_extensions,
    integer_to_words,
)
from addons.base.models import ResCurrency

apply_account_check_printing_currency_extensions()


class TestIntegerToWords:
    def test_zero(self):
        assert integer_to_words(0) == 'cero'

    def test_units(self):
        assert integer_to_words(7) == 'siete'

    def test_apocope_before_a_noun(self):
        # ≙ "un" no "uno" — la forma que precede a "PESOS".
        assert integer_to_words(1) == 'un'

    def test_teens(self):
        assert integer_to_words(16) == 'dieciséis'

    def test_twenties(self):
        assert integer_to_words(21) == 'veintiuno'

    def test_tens_compound_keeps_the_apocope(self):
        assert integer_to_words(31) == 'treinta y un'

    def test_hundred_exact_is_cien_not_ciento(self):
        assert integer_to_words(100) == 'cien'

    def test_hundreds_compound(self):
        assert integer_to_words(521) == 'quinientos veintiuno'

    def test_thousand_exact_has_no_leading_un(self):
        assert integer_to_words(1000) == 'mil'

    def test_thousands_compound(self):
        assert integer_to_words(2024) == 'dos mil veinticuatro'

    def test_million_exact(self):
        assert integer_to_words(1_000_000) == 'un millón'

    def test_millions_compound(self):
        assert integer_to_words(2_500_000) == 'dos millones quinientos mil'

    def test_out_of_range_degrades_to_digits(self):
        # ≙ el techo declarado del conversor (0..999 999 999).
        assert integer_to_words(1_000_000_000) == '1000000000'

    def test_negative_degrades_to_digits(self):
        assert integer_to_words(-5) == '-5'


class TestAmountToText:
    """``amount_to_text`` colgado sobre ``ResCurrency`` — sin necesidad de
    guardar la instancia: el conversor no lee ningún campo de ``self``
    (divergencia declarada: siempre dice "PESOS", ver el docstring del
    módulo bajo prueba)."""

    def test_zero(self):
        currency = ResCurrency()
        assert currency.amount_to_text(Decimal('0.00')) == 'CERO PESOS 00/100 M.N.'

    def test_with_cents(self):
        currency = ResCurrency()
        assert currency.amount_to_text(Decimal('100.50')) == 'CIEN PESOS 50/100 M.N.'

    def test_rounds_half_up_on_the_exact_half_cent(self):
        currency = ResCurrency()
        assert currency.amount_to_text(Decimal('10.005')) == 'DIEZ PESOS 01/100 M.N.'

    def test_thousands(self):
        currency = ResCurrency()
        text = currency.amount_to_text(Decimal('2024.00'))
        assert text == 'DOS MIL VEINTICUATRO PESOS 00/100 M.N.'

    def test_accepts_a_plain_int_too(self):
        currency = ResCurrency()
        assert currency.amount_to_text(100) == 'CIEN PESOS 00/100 M.N.'
