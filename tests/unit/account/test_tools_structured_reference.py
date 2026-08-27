"""Referencias estructuradas de pago -- validacion y formato.

Cubre ``addons/account/tools/structured_reference.py``, portacion pura sin
ORM (tarea #398, hallazgo H-API-682). Los tres algoritmos vendorizados
(MOD 97-10 ISO 7064, Luhn, ISO 11649) reemplazan a la libreria ``stdnum``
ausente de este arbol -- ver la divergencia declarada en el docstring del
modulo bajo prueba.
"""
import pytest

from addons.account.tools.structured_reference import (
    format_structured_reference_iso,
    is_valid_structured_reference,
    is_valid_structured_reference_be,
    is_valid_structured_reference_fi,
    is_valid_structured_reference_for_country,
    is_valid_structured_reference_iso,
    is_valid_structured_reference_nl,
    is_valid_structured_reference_no_se,
    is_valid_structured_reference_si,
    sanitize_structured_reference,
)

pytestmark = [pytest.mark.unit]


class TestSanitizeStructuredReference:
    """Quita espacios y, solo en el patron belga, los separadores."""

    def test_strips_whitespace(self):
        assert sanitize_structured_reference(' RF18 1234 5678 9  ') == 'RF18123456789'

    def test_strips_belgian_plus_delimiters(self):
        assert sanitize_structured_reference('+++020/3430/57642+++') == '020343057642'

    def test_strips_belgian_star_delimiters(self):
        assert sanitize_structured_reference('***020/3430/57642***') == '020343057642'

    def test_a_non_belgian_pattern_only_loses_whitespace(self):
        # No matchea el patron belga (3/4/5 digitos) -> solo se quita el
        # espacio, las barras sobreviven.
        assert sanitize_structured_reference('12/34/567') == '12/34/567'


class TestFormatStructuredReferenceIso:
    """El ejemplo EXACTO del docstring de la fuente
    (``odoo19c: addons/account/tools/structured_reference.py:28``): la
    prueba mas fuerte de fidelidad del algoritmo MOD 97-10 vendorizado.
    """

    def test_the_source_docstring_example(self):
        assert format_structured_reference_iso('123456789') == 'RF18 1234 5678 9'

    def test_formatted_reference_round_trips_as_valid(self):
        formatted = format_structured_reference_iso('123456789')
        assert is_valid_structured_reference_iso(formatted)

    def test_groups_digits_in_blocks_of_four(self):
        # RF + 2 digitos de control + los digitos originales en bloques de 4
        formatted = format_structured_reference_iso('1')
        assert formatted.startswith('RF')
        assert formatted.endswith(' 1')


class TestIso11649Validity:
    def test_a_reference_without_the_rf_prefix_is_invalid(self):
        assert not is_valid_structured_reference_iso('18539007547034')

    def test_a_reference_with_wrong_check_digits_is_invalid(self):
        assert not is_valid_structured_reference_iso('RF00539007547034')


class TestBelgianStructuredReference:
    """``(10 digitos)(2 digitos de control)`` con
    ``check == numero % 97`` (con el caso especial de resto 0 -> 97).
    """

    def test_a_reference_whose_check_matches_the_modulo_is_valid(self):
        # 0000000001 % 97 == 1
        assert is_valid_structured_reference_be('000000000101')

    def test_a_reference_with_a_wrong_check_digit_is_invalid(self):
        assert not is_valid_structured_reference_be('000000000199')

    def test_wrong_length_is_invalid(self):
        assert not is_valid_structured_reference_be('123')


class TestFinnishStructuredReference:
    """Suma ponderada (7,3,1) ciclica sobre los digitos, en reversa."""

    def test_a_known_valid_reference(self):
        # digitos base '1' con 0 de relleno -> total=7*1=7, check=(10-7)%10=3
        assert is_valid_structured_reference_fi('13')

    def test_a_wrong_check_digit_is_invalid(self):
        assert not is_valid_structured_reference_fi('19')


class TestNoSeStructuredReference:
    """Puramente numerica + Luhn."""

    def test_a_luhn_valid_number_is_valid(self):
        assert is_valid_structured_reference_no_se('79927398713')

    def test_a_luhn_invalid_number_is_invalid(self):
        assert not is_valid_structured_reference_no_se('79927398710')

    def test_a_non_numeric_string_is_invalid(self):
        assert not is_valid_structured_reference_no_se('79A27398713')


class TestDutchStructuredReference:
    """Longitud 7 siempre valida; 9-16 (salvo 15) exige el digito de control
    ponderado.
    """

    def test_a_seven_digit_reference_is_always_valid(self):
        assert is_valid_structured_reference_nl('1234567')

    def test_a_fifteen_digit_reference_is_never_valid(self):
        assert not is_valid_structured_reference_nl('1' * 15)

    def test_a_bad_length_is_invalid(self):
        assert not is_valid_structured_reference_nl('12345678')  # 8 digitos


class TestSlovenianStructuredReference:
    def test_without_the_si01_prefix_is_invalid(self):
        assert not is_valid_structured_reference_si('12-34-567')

    def test_with_more_than_two_hyphens_is_invalid(self):
        assert not is_valid_structured_reference_si('SI0112-34-56-78')

    def test_without_the_three_hyphenated_groups_is_invalid(self):
        assert not is_valid_structured_reference_si('SI01123456')


class TestIsValidStructuredReference:
    """El OR de todos los paises + ISO 11649 -- vacio nunca es valido."""

    def test_empty_reference_is_invalid(self):
        assert not is_valid_structured_reference('')

    def test_none_reference_is_invalid(self):
        assert not is_valid_structured_reference(None)

    def test_a_valid_iso_reference_is_valid(self):
        formatted = format_structured_reference_iso('123456789')
        assert is_valid_structured_reference(formatted)


class TestIsValidStructuredReferenceForCountry:
    """Despacha por pais; sin pais conocido cae a ISO 11649."""

    def test_dispatches_to_the_country_specific_check(self):
        assert is_valid_structured_reference_for_country('1234567', 'NL')

    def test_country_code_is_case_insensitive(self):
        assert is_valid_structured_reference_for_country('1234567', 'nl')

    def test_unknown_country_falls_back_to_iso(self):
        formatted = format_structured_reference_iso('123456789')
        assert is_valid_structured_reference_for_country(formatted, 'XX')
