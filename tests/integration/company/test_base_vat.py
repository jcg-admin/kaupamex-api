"""base_vat — validación de RFC (DEC-01, ~base_vat de Odoo).

Valida el formato + fecha del RFC del SAT y su enganche en ``ResPartner.vat``
— fiel a la referencia: ``base_vat`` extiende ``res.partner``
(``odoo19c: base_vat/models/res_partner.py:92``, ``_inherit``); la compañía
lo lee por delegación (``ResCompany.vat`` es property al partner).
"""
import pytest
from django.core.exceptions import ValidationError

from addons.base.models import ResPartner
from addons.base_vat.validators import validate_rfc, validate_tax_id

pytestmark = pytest.mark.django_db


# --- validador puro (sin DB) ------------------------------------------------

@pytest.mark.parametrize('rfc', [
    'XAXX010101000',   # genérico nacional (13, física)
    'XEXX010101000',   # genérico extranjero (13)
    'ABC010101AB1',    # moral (12)
    'ABCD991231XY9',   # física (13), 1999-12-31
    '',                # vacío se ignora (campo opcional)
])
def test_valid_rfc_passes(rfc):
    validate_rfc(rfc)  # no lanza


@pytest.mark.parametrize('rfc', [
    'ABC12',            # muy corto
    '1234567890123',    # sin letras
    'ABCDE010101AB1',   # 5 letras (14 chars)
    'ABC991301AB1',     # mes 13 inválido
    'ABC010132AB1',     # día 32 inválido
])
def test_invalid_rfc_raises(rfc):
    with pytest.raises(ValidationError):
        validate_rfc(rfc)


def test_dispatcher_unknown_country_no_restriction():
    # País sin validador (paridad Odoo): no falla.
    validate_tax_id('cualquier-cosa', country='US')
    validate_tax_id('XAXX010101000', country='MX')  # MX sí valida


def test_normalizes_lowercase():
    validate_rfc('xaxx010101000')  # minúsculas: se normaliza, no lanza


# --- enganche en ResPartner.vat (el _inherit del addon) ---------------------

def test_partner_vat_field_has_validator():
    field = ResPartner._meta.get_field('vat')
    assert validate_rfc in field.validators


def test_partner_full_clean_rejects_bad_rfc():
    p = ResPartner(name='T', vat='NOPE')
    with pytest.raises(ValidationError) as exc:
        p.full_clean()
    assert 'vat' in exc.value.message_dict


def test_partner_full_clean_accepts_good_rfc(db):
    p = ResPartner(name='T', vat='XAXX010101000')
    try:
        p.full_clean()
    except ValidationError as exc:
        assert 'vat' not in exc.message_dict
