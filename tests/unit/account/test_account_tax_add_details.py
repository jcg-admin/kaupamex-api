"""Los detalles de impuestos de una base-line, en las dos monedas.

≙ ``_add_tax_details_in_base_line`` y ``_add_tax_details_in_base_lines``
(``odoo19c: addons/account/models/account_tax.py:1737-1823``, LGPL-3), y la
forma de lo que ``_get_tax_details`` devuelve (``:1320-1336``), que es lo que
la envoltura consume.

El caso de referencia: 100 por 2 con 10 % de descuento y un 16 %, en una
moneda con tasa 2 frente a la de la compañía. El precio neto es 90, la base
180 en moneda extranjera y 90 en local, el impuesto 28.80 y 14.40.
"""

from decimal import Decimal

import pytest

from addons.account.models import AccountTax
from addons.base.models import ResCompany
from addons.base.models.res_currency import ResCurrency

pytestmark = pytest.mark.django_db

SOURCE_TAX_DATA_KEYS = {'tax', 'taxes', 'group', 'batch', 'tax_amount',
                        'price_include', 'base_amount', 'is_reverse_charge'}


@pytest.fixture
def currency(db):
    currency, _ = ResCurrency.objects.get_or_create(
        name='MXN', defaults={'symbol': '$'})
    return currency


@pytest.fixture
def company(db, currency):
    return ResCompany.objects.create(code='detalles', name='Detalles',
                                     currency=currency)


@pytest.fixture
def tax(company):
    return AccountTax.objects.create(name='IVA 16', amount=Decimal('16'),
                                     company=company)


def _base_line(tax, currency, **overrides):
    values = {
        'tax_ids': AccountTax.objects.filter(pk=tax.pk),
        'price_unit': 100.0, 'quantity': 2.0, 'discount': 10.0,
        'currency_id': currency, 'rate': 2.0, **overrides,
    }
    return AccountTax._prepare_base_line_for_taxes_computation(
        {'id': 1}, **values)


def test_the_engine_returns_the_source_projection(tax):
    details = AccountTax.objects.filter(pk=tax.pk)._get_tax_details(
        Decimal('90'), quantity=Decimal('2'))
    tax_data = details['taxes_data'][0]
    assert set(tax_data) == SOURCE_TAX_DATA_KEYS
    assert tax_data['base_amount'] == Decimal('180')
    assert tax_data['is_reverse_charge'] is False


def test_round_per_line_rounds_the_local_amounts(company, currency, tax):
    base_line = _base_line(tax, currency)
    AccountTax._add_tax_details_in_base_line(
        base_line, company, rounding_method='round_per_line')
    details = base_line['tax_details']
    assert details['raw_total_excluded_currency'] == Decimal('180')
    assert details['raw_total_excluded'] == Decimal('90')
    assert details['raw_total_included_currency'] == Decimal('208.80')
    assert details['raw_total_included'] == Decimal('104.40')
    [tax_data] = details['taxes_data']
    assert tax_data['raw_tax_amount_currency'] == Decimal('28.80')
    assert tax_data['raw_tax_amount'] == Decimal('14.40')
    assert tax_data['raw_base_amount_currency'] == Decimal('180')
    assert tax_data['raw_base_amount'] == Decimal('90')
    assert tax_data['tax'] == tax


def test_round_per_line_rounds_an_inexact_local_amount(company, currency,
                                                       tax):
    """Con tasa 7 lo local no sale exacto (180/7, 28.80/7): ``round_per_line``
    lo deja en dos decimales; sin el redondeo serían 25.714… y 4.114…"""
    base_line = _base_line(tax, currency, rate=7.0)
    AccountTax._add_tax_details_in_base_line(
        base_line, company, rounding_method='round_per_line')
    details = base_line['tax_details']
    assert details['raw_total_excluded'] == Decimal('25.71')
    assert details['taxes_data'][0]['raw_tax_amount'] == Decimal('4.11')


def test_the_company_method_applies_when_none_is_given(company, currency,
                                                       tax):
    """``round_globally`` (el de la compañía) no redondea lo local: 90/7."""
    company.tax_calculation_rounding_method = 'round_globally'
    base_line = _base_line(tax, currency, quantity=1.0)
    base_line['rate'] = 7.0
    AccountTax._add_tax_details_in_base_line(base_line, company)
    local = base_line['tax_details']['raw_total_excluded']
    assert local != round(local, 2)


def test_non_deductible_drops_the_reverse_charge_part(company, currency, tax,
                                                      monkeypatch):
    """La rama ``non_deductible`` (``:1777-1784``): la parte de cargo
    revertido sale de ``taxes_data`` y su importe del total incluido. El
    motor de este árbol no produce cargo revertido, así que su resultado se
    sustituye por uno que lo trae."""
    def engine(self, *args, **kwargs):
        return {
            'total_excluded': Decimal('100'),
            'total_included': Decimal('100'),
            'taxes_data': [
                {'tax': tax, 'tax_amount': Decimal('16'),
                 'base_amount': Decimal('100'), 'is_reverse_charge': False},
                {'tax': tax, 'tax_amount': Decimal('-16'),
                 'base_amount': Decimal('100'), 'is_reverse_charge': True},
            ],
        }

    monkeypatch.setattr(type(AccountTax.objects.none()), '_get_tax_details',
                        engine)
    base_line = _base_line(tax, currency, special_type='non_deductible')
    base_line['rate'] = 1.0
    AccountTax._add_tax_details_in_base_line(
        base_line, company, rounding_method='round_per_line')
    details = base_line['tax_details']
    assert len(details['taxes_data']) == 1
    assert details['raw_total_included_currency'] == Decimal('116')


def test_the_shortcut_fills_every_line(company, currency, tax):
    lines = [_base_line(tax, currency), _base_line(tax, currency)]
    AccountTax._add_tax_details_in_base_lines(lines, company)
    assert all('tax_details' in line for line in lines)
