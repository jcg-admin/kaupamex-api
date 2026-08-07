"""Contrato de ``account_qr_code_sepa.tools`` — el vendor local de
``account/tools/structured_reference.py`` (ver el docstring del módulo para
la medición de por qué se vendoriza en vez de importarse).

Sin ``pytest.mark.django_db``: estas funciones son puro Python (regex,
aritmética entera), sin ORM de por medio — los mismos dos vectores que la
referencia usa en ``test_get_qr_vals_communication`` más los casos límite de
los dos primitivos reimplementados (``_luhn_is_valid``, ``_iso11649_is_valid``,
sustitutos de ``stdnum.luhn``/``stdnum.iso11649`` — ver la sección
"Qué se porta aquí" del módulo).
"""
from addons.account_qr_code_sepa.tools import (
    SEPA_ZONE_COUNTRY_CODES,
    _iso11649_is_valid,
    _luhn_is_valid,
    is_valid_structured_reference,
    is_valid_structured_reference_be,
    is_valid_structured_reference_iso,
    is_valid_structured_reference_nl,
    sanitize_structured_reference,
)


class TestSepaZoneCountryCodes:
    def test_tiene_los_49_paises_del_fixture(self):
        assert len(SEPA_ZONE_COUNTRY_CODES) == 49

    def test_incluye_espana_y_reino_unido(self):
        # 'GB', no 'UK' — el id XML de la referencia es 'uk' pero su campo
        # `code` real es 'gb' (odoo19c: res_country_data.xml:1497-1500).
        assert 'ES' in SEPA_ZONE_COUNTRY_CODES
        assert 'GB' in SEPA_ZONE_COUNTRY_CODES
        assert 'UK' not in SEPA_ZONE_COUNTRY_CODES

    def test_no_incluye_paises_fuera_de_sepa(self):
        assert 'US' not in SEPA_ZONE_COUNTRY_CODES
        assert 'MX' not in SEPA_ZONE_COUNTRY_CODES


class TestSanitizeStructuredReference:
    def test_quita_espacios(self):
        assert sanitize_structured_reference(' RF18 1234 5678 9  ') == 'RF18123456789'

    def test_normaliza_el_formato_belga_con_cruces(self):
        assert sanitize_structured_reference('+++020/3430/57642+++') == '020343057642'

    def test_normaliza_el_formato_belga_con_asteriscos(self):
        assert sanitize_structured_reference('***020/3430/57642***') == '020343057642'


class TestIsValidStructuredReference:
    def test_un_comentario_libre_no_es_una_referencia_estructurada(self):
        """≙ primer vector de ``test_get_qr_vals_communication``."""
        assert is_valid_structured_reference('A free communication') is False

    def test_una_referencia_nl_valida_con_espacios_es_valida(self):
        """≙ segundo vector: NL Structured reference."""
        assert is_valid_structured_reference(' 5 000 0567 89012345 ') is True

    def test_vacio_o_none_no_es_valido(self):
        assert is_valid_structured_reference('') is False
        assert is_valid_structured_reference(None) is False


class TestIsValidStructuredReferenceBe:
    def test_referencia_belga_valida_por_modulo_97(self):
        # 10 dígitos base + 2 de control == base % 97 — 234567890 % 97 == 65
        # (verificado: `python3 -c "print(234567890 % 97)"` → 65).
        assert is_valid_structured_reference_be('023456789065') is True

    def test_referencia_belga_con_control_incorrecto_es_invalida(self):
        assert is_valid_structured_reference_be('023456789066') is False

    def test_longitud_incorrecta_es_invalida(self):
        # ``re.fullmatch`` sin match da ``None``, y la referencia hace
        # ``return be_ref and ...`` — el corto-circuito propaga ``None``, no
        # ``False``. Fiel al original (verbatim), no una laxitud del puerto.
        assert is_valid_structured_reference_be('12345') is None


class TestLuhnIsValid:
    def test_vector_conocido_valido(self):
        # 79927398713 — vector de prueba estándar del algoritmo de Luhn.
        assert _luhn_is_valid('79927398713') is True

    def test_vector_conocido_invalido(self):
        assert _luhn_is_valid('79927398710') is False

    def test_no_numerico_es_invalido(self):
        assert _luhn_is_valid('79927A98713') is False

    def test_vacio_es_invalido(self):
        assert _luhn_is_valid('') is False


class TestIso11649IsValid:
    def test_vector_conocido_valido(self):
        assert _iso11649_is_valid('RF18539007547034') is True
        assert is_valid_structured_reference_iso('RF18539007547034') is True

    def test_digito_de_control_incorrecto_es_invalido(self):
        assert _iso11649_is_valid('RF18539007547035') is False

    def test_sin_prefijo_rf_es_invalido(self):
        assert _iso11649_is_valid('AB18539007547034') is False

    def test_acepta_minusculas(self):
        assert _iso11649_is_valid('rf18539007547034') is True


class TestIsValidStructuredReferenceNl:
    def test_referencia_de_siete_digitos_siempre_es_valida(self):
        assert is_valid_structured_reference_nl('1234567') is True

    def test_dieciseis_digitos_del_vector_de_la_referencia(self):
        assert is_valid_structured_reference_nl('5000056789012345') is True

    def test_longitud_15_es_invalida(self):
        # La referencia excluye explícitamente 15 dígitos (ni la forma de 7
        # ni la de 9-14/16 la cubre).
        assert is_valid_structured_reference_nl('123456789012345') is False
