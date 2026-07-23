"""Validación de cuenta bancaria — addons.base_bank (DEC-01, ~base_iban Odoo).

Odoo ``base_iban`` agrega ``check_iban`` a ``res.partner.bank`` con un
dispatcher (``validate_iban``) que verifica longitud por país y el **dígito
verificador** IBAN (mod-97, ISO 13616) — ver
``base_iban/models/res_partner_bank.py`` (``validate_iban`` / ``_check_iban``).
Aquí se replica el patrón dispatcher con un validador por país; MX = **CLABE**
(Clave Bancaria Estandarizada, norma del Banco de México / ABM).

CLABE — 18 dígitos:
- 3 dígitos de **banco** + 3 de **plaza** + 11 de **cuenta** + 1 **dígito
  verificador**.
- El dígito verificador se calcula sobre los primeros 17 dígitos con pesos
  ``[3, 7, 1]`` cíclicos: por cada dígito ``(dígito × peso) mod 10``; se suman
  esos productos; ``verificador = (10 − (suma mod 10)) mod 10``.

A diferencia del RFC (ver ``base_vat`` H-API-VAT-02), el dígito verificador de
la CLABE **sí** se valida: su algoritmo es determinista y estándar (mod-10
ponderado), sin riesgo de falsos rechazos — igual que Odoo valida el mod-97 del
IBAN.
"""
import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# Exactamente 18 dígitos (se permiten espacios/guiones de formato, se limpian).
_CLABE_RE = re.compile(r'^[0-9]{18}$')
# Pesos cíclicos del dígito verificador CLABE.
_CLABE_WEIGHTS = (3, 7, 1)


def _clabe_check_digit(first17):
    """Dígito verificador CLABE (mod-10 ponderado) de los 17 primeros dígitos."""
    total = 0
    for i, ch in enumerate(first17):
        total += (int(ch) * _CLABE_WEIGHTS[i % 3]) % 10
    return (10 - (total % 10)) % 10


def validate_clabe(value):
    """Valida una CLABE mexicana (18 dígitos + verificador). Vacío se ignora."""
    if not value:
        return
    v = re.sub(r'[\s-]', '', str(value))
    if not _CLABE_RE.match(v):
        raise ValidationError(
            _('CLABE inválida: se esperan exactamente 18 dígitos.'),
            code='invalid_clabe',
        )
    if int(v[17]) != _clabe_check_digit(v[:17]):
        raise ValidationError(
            _('CLABE inválida: el dígito verificador no coincide.'),
            code='invalid_clabe_checkdigit',
        )


# Dispatcher por país (Odoo ``validate_iban`` valida por longitud+checksum del
# país del prefijo). Extensible: agregar entradas por país (IBAN, US routing,
# etc.) conforme se necesiten.
_VALIDATORS = {
    'MX': validate_clabe,
}


def validate_bank_account(value, country='MX'):
    """Valida ``value`` como cuenta bancaria del ``country`` (default MX).

    Si no hay validador para el país, no restringe (paridad con Odoo: países sin
    reglas registradas no fallan)."""
    validator = _VALIDATORS.get((country or 'MX').upper())
    if validator is not None:
        validator(value)
