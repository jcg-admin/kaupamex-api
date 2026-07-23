"""base_bank — validación de CLABE (DEC-01, ~base_iban de Odoo).

Valida el formato (18 dígitos) + el dígito verificador mod-10 ponderado de la
CLABE mexicana, y el dispatcher por país. Test puro (sin DB).
"""
import pytest
from django.core.exceptions import ValidationError

from addons.base_bank.validators import (
    _clabe_check_digit,
    validate_bank_account,
    validate_clabe,
)


# CLABEs válidas de referencia pública (18 dígitos, verificador correcto).
@pytest.mark.parametrize('clabe', [
    '002010077777777771',
    '032180000118359719',
    '646180157042875763',
    '',                       # vacío se ignora (campo opcional)
])
def test_valid_clabe_passes(clabe):
    validate_clabe(clabe)  # no lanza


@pytest.mark.parametrize('clabe', [
    '00201007777777777',      # 17 dígitos (corta)
    '0020100777777777712',    # 19 dígitos (larga)
    '00201007777777777A',     # no numérica
    '002010077777777770',     # verificador incorrecto (debería ser 1)
])
def test_invalid_clabe_raises(clabe):
    with pytest.raises(ValidationError):
        validate_clabe(clabe)


def test_check_digit_algorithm():
    # Verificador de una CLABE conocida: los primeros 17 dígitos de
    # 002010077777777771 dan verificador 1.
    assert _clabe_check_digit('00201007777777777') == 1


def test_normalizes_spaces_and_dashes():
    validate_clabe('0020 1007 7777 7777 71')   # espacios: se limpian, válida
    validate_clabe('002-010-077777777771')     # guiones: se limpian, válida


def test_dispatcher_unknown_country_no_restriction():
    # País sin validador (paridad Odoo): no falla.
    validate_bank_account('cualquier-cosa', country='US')
    validate_bank_account('002010077777777771', country='MX')  # MX sí valida


def test_dispatcher_mx_default_rejects_bad_clabe():
    with pytest.raises(ValidationError):
        validate_bank_account('002010077777777770')  # default MX, verificador malo
