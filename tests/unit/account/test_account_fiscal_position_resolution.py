"""Resolución automática de posición fiscal.

≙ ``odoo19c: addons/account/models/partner.py:208-280,873-876``.
"""
import pytest

from addons.account.models import AccountFiscalPosition
from addons.base.models import ResCompany, ResCountry, ResPartner
from orm.environments import company_scope

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def company():
    company = ResCompany.objects.create(code='fpos', name='FPOS')
    with company_scope(company):
        yield company


@pytest.fixture
def mexico():
    return ResCountry.objects.get(code__iexact='MX')


def _fpos(company, name, sequence=10, **values):
    return AccountFiscalPosition.objects.create(
        name=name, company=company, auto_apply=True, sequence=sequence,
        **values)


def _partner(**values):
    return ResPartner.objects.create(name='Proveedor', **values)


def test_no_partner_gives_the_empty_position(company):
    assert not AccountFiscalPosition._get_fiscal_position(None).pk


def test_the_manual_position_of_the_partner_wins(company, mexico):
    _fpos(company, 'Automática', country=mexico)
    manual = AccountFiscalPosition.objects.create(
        name='Manual', company=company)
    partner = _partner(country=mexico, property_account_position_id=manual)
    assert AccountFiscalPosition._get_fiscal_position(partner) == manual


def test_a_partner_without_country_gets_none(company, mexico):
    _fpos(company, 'Automática', country=mexico)
    assert not AccountFiscalPosition._get_fiscal_position(_partner()).pk


def test_the_country_selects_the_automatic_position(company, mexico):
    match = _fpos(company, 'México', country=mexico)
    assert AccountFiscalPosition._get_fiscal_position(
        _partner(country=mexico)) == match


def test_vat_required_skips_a_partner_without_vat(company, mexico):
    _fpos(company, 'Con RFC', sequence=1, country=mexico, vat_required=True)
    fallback = _fpos(company, 'Sin RFC', sequence=2, country=mexico)
    assert AccountFiscalPosition._get_fiscal_position(
        _partner(country=mexico)) == fallback


def test_the_zip_range_is_checked(company, mexico):
    _fpos(company, 'Norte', sequence=1, country=mexico,
          zip_from='80000', zip_to='89999')
    rest = _fpos(company, 'Resto', sequence=2, country=mexico)
    assert AccountFiscalPosition._get_fiscal_position(
        _partner(country=mexico, zip='06000')) == rest


def test_sequence_orders_positions_of_the_same_company(company, mexico):
    first = _fpos(company, 'Primera', sequence=1, country=mexico)
    _fpos(company, 'Segunda', sequence=2, country=mexico)
    assert AccountFiscalPosition._get_fiscal_position(
        _partner(country=mexico)) == first


def test_a_position_of_another_company_is_ignored(company, mexico):
    other = ResCompany.objects.create(code='otra', name='Otra')
    _fpos(other, 'Ajena', country=mexico)
    assert not AccountFiscalPosition._get_fiscal_position(
        _partner(country=mexico)).pk


# --- base_vat endurece el requisito con VIES (odoo19c: base_vat :952-962) ---


@pytest.fixture
def eu_company():
    spain = ResCountry.objects.get(code__iexact='ES')
    company = ResCompany.objects.create(
        code='fpos-eu', name='FPOS EU', country=spain, vat_check_vies=True)
    with company_scope(company):
        yield company


def test_the_eu_company_has_the_eu_group(eu_company):
    """Precondición del caso VIES: sin el grupo la rama no se ejerce."""
    assert 'EU' in (eu_company.country.country_group_codes or [])


@pytest.mark.parametrize(
    'vies_valid, expected', [(False, 'fallback'), (True, 'vat')])
def test_vies_hardens_the_vat_requirement(eu_company, vies_valid, expected):
    france = ResCountry.objects.get(code__iexact='FR')
    positions = {
        'vat': _fpos(eu_company, 'Intracomunitaria', sequence=1,
                     country=france, vat_required=True),
        'fallback': _fpos(eu_company, 'Resto', sequence=2, country=france),
    }
    partner = _partner(country=france, vat='FR23334175221',
                       vies_valid=vies_valid)
    assert partner._get_vat_required_valid(company=eu_company) is vies_valid
    assert AccountFiscalPosition._get_fiscal_position(
        partner) == positions[expected]


def test_without_vies_the_vat_alone_satisfies_the_requirement(company, mexico):
    partner = _partner(country=mexico, vat='XAXX010101000', vies_valid=False)
    assert partner._get_vat_required_valid(company=company) is True
