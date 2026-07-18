"""Validación de identificador fiscal — addons.base_vat (DEC-01, ~base_vat Odoo).

Odoo ``base_vat`` agrega ``check_vat`` a ``res.partner`` con un dispatcher por
país (``check_vat_XX``) — ver ``base_vat/models/res_partner.py:185`` (``check_vat``)
y el mapa ``_ref_vat``. Aquí se replica el patrón dispatcher con un validador por
país; MX = **RFC** (Registro Federal de Contribuyentes, SAT).

RFC — formato oficial SAT:
- Persona **moral**: 3 letras + AAMMDD + homoclave (3) = **12** caracteres.
- Persona **física**: 4 letras + AAMMDD + homoclave (3) = **13** caracteres.

Se valida **formato + fecha embebida** (nunca rechaza un RFC bien formado, sólo
atrapa los malformados). El **dígito verificador** de la homoclave (algoritmo
SAT) queda como endurecimiento follow-up (ver H-API-VAT-02) para no arriesgar
falsos rechazos por una implementación imprecisa del checksum.
"""
import re
from datetime import datetime

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# 3-4 letras (incluye Ñ y & del SAT) + 6 dígitos de fecha + 3 alfanuméricos.
_RFC_RE = re.compile(r'^[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}$')


def validate_rfc(value):
    """Valida un RFC mexicano (formato + fecha). Vacío se ignora (campo opcional)."""
    if not value:
        return
    v = str(value).strip().upper()
    if not _RFC_RE.match(v):
        raise ValidationError(
            _('RFC inválido: se esperan 12 (persona moral) o 13 (persona '
              'física) caracteres con el formato del SAT.'),
            code='invalid_rfc',
        )
    # La fecha AAMMDD ocupa 6 posiciones tras las letras (len - 9 = nº de letras).
    n = len(v) - 9
    yymmdd = v[n:n + 6]
    try:
        datetime.strptime(yymmdd, '%y%m%d')
    except ValueError:
        raise ValidationError(
            _('RFC inválido: la fecha embebida (%(d)s) no es una fecha válida.')
            % {'d': yymmdd},
            code='invalid_rfc_date',
        )


# Dispatcher por país (Odoo ``check_vat_XX``). Extensible: agregar entradas por
# país conforme se necesiten (US EIN, CO NIT, etc.).
_VALIDATORS = {
    'MX': validate_rfc,
}


def validate_tax_id(value, country='MX'):
    """Valida ``value`` como identificador fiscal del ``country`` (default MX).

    Si no hay validador para el país, no restringe (paridad con Odoo: países sin
    ``check_vat_XX`` no fallan)."""
    validator = _VALIDATORS.get((country or 'MX').upper())
    if validator is not None:
        validator(value)
