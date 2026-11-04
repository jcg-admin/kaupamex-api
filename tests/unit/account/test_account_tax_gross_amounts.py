"""Los importes brutos y el redondeo de los importes crudos de las líneas.

≙ ``_get_delta_amount_to_reach_target``, ``_round_raw_total_excluded``,
``_get_gross_total_without_tax``, ``_get_price_unit_without_tax``,
``_get_discount_amount_without_tax``,
``_add_and_round_raw_gross_total_excluded_and_discount``,
``_round_raw_gross_total_excluded_and_discount`` y ``_round_raw_tax_amounts``
(``odoo19c: addons/account/models/account_tax.py:4445-4949``, LGPL-3). Los
consume el EDI para informar precio bruto y descuento por línea.

Las cifras se derivan de la aritmética de la fuente: el delta mínimo para que
un crudo redondee a su objetivo, el bruto como neto entre ``1 - descuento``,
y el reparto de los centavos que el redondeo por línea pierde.
"""

from decimal import Decimal

import pytest

from addons.account.models import AccountTax
from addons.base.models import ResCompany
from addons.base.models.res_currency import ResCurrency

pytestmark = pytest.mark.django_db

D = Decimal


@pytest.fixture
def currency(db):
    currency, _ = ResCurrency.objects.get_or_create(
        name='MXN', defaults={'symbol': '$'})
    return currency


@pytest.fixture
def company(db, currency):
    return ResCompany.objects.create(code='bruto', name='Bruto',
                                     currency=currency)


def _lines(currency, count, taxes=None, **values):
    taxes = taxes if taxes is not None else AccountTax.objects.none()
    values = {'rate': 1.0, **values}
    return [
        AccountTax._prepare_base_line_for_taxes_computation(
            {'id': index}, tax_ids=taxes, currency_id=currency, **values)
        for index in range(1, count + 1)
    ]


def _rounded(base_lines, company):
    for base_line in base_lines:
        AccountTax._add_tax_details_in_base_line(
            base_line, company, rounding_method='round_globally')
    AccountTax._round_base_lines_tax_details(base_lines, company)
    return base_lines


# -- el delta mínimo hacia un objetivo (:4445-4486) -------------------------

@pytest.mark.parametrize('target, raw, expected', [
    (D('10.00'), D('10.006'), D('-0.001001')),
    (D('10.00'), D('9.990'), D('0.005')),
    (D('10.00'), D('10.002'), D('0')),
    (D('-10.00'), D('-10.006'), D('0.001001')),
])
def test_the_delta_is_the_smallest_that_reaches_the_target(
        currency, target, raw, expected):
    delta = AccountTax._get_delta_amount_to_reach_target(
        target_amount=target, target_currency=currency,
        raw_current_amount=raw, raw_current_amount_precision_digits=6)
    assert delta == expected
    assert currency.round(raw + delta) == target


# -- el bruto, el precio y el descuento de una línea (:4560-4644) -----------

def test_the_gross_total_undoes_the_discount(company, currency):
    [base_line] = _rounded(
        _lines(currency, 1, price_unit=100.0, quantity=2.0, discount=10.0),
        company)
    gross = AccountTax._get_gross_total_without_tax(base_line, company)
    assert gross == D('200')
    assert AccountTax._get_price_unit_without_tax(
        base_line, company, gross) == D('100')
    assert AccountTax._get_discount_amount_without_tax(
        base_line, company, gross) == D('20')


def test_a_full_discount_falls_back_to_price_by_quantity(company, currency):
    [base_line] = _rounded(
        _lines(currency, 1, price_unit=100.0, quantity=2.0, discount=100.0,
               rate=2.0),
        company)
    assert AccountTax._get_gross_total_without_tax(
        base_line, company) == D('200')
    assert AccountTax._get_gross_total_without_tax(
        base_line, company, in_foreign_currency=False) == D('100')


def test_without_quantity_the_price_unit_is_the_gross(company, currency):
    [base_line] = _rounded(
        _lines(currency, 1, price_unit=100.0, quantity=0.0), company)
    assert AccountTax._get_price_unit_without_tax(
        base_line, company, D('50')) == D('50')
    assert AccountTax._get_price_unit_without_tax(
        base_line, company, D('0')) == D('100')


# -- añadir y redondear el bruto (:4647-4846) -------------------------------

def test_the_gross_amounts_land_in_the_tax_details(company, currency):
    [base_line] = _rounded(
        _lines(currency, 1, price_unit=100.0, quantity=2.0, discount=10.0),
        company)
    AccountTax._add_and_round_raw_gross_total_excluded_and_discount(
        [base_line], company)
    details = base_line['tax_details']
    assert details['raw_gross_total_excluded_currency'] == D('200')
    assert details['raw_gross_price_unit_currency'] == D('100')
    assert details['raw_discount_amount_currency'] == D('20')


def test_the_rounded_gross_and_discount_add_up_to_the_document(
        company, currency):
    """Tres líneas de 1.115 con un 10 %: cada bruto redondea a 1.12 (3.36),
    pero el documento sin impuesto es 3.01 y el descuento 0.33, así que el
    bruto debe sumar 3.34 y el reparto le quita dos centavos."""
    base_lines = _rounded(
        _lines(currency, 3, price_unit=1.115, quantity=1.0, discount=10.0),
        company)
    AccountTax._add_and_round_raw_gross_total_excluded_and_discount(
        base_lines, company)
    AccountTax._round_raw_gross_total_excluded_and_discount(
        base_lines, company)
    gross = [line['tax_details']['gross_total_excluded_currency']
             for line in base_lines]
    discounts = [line['tax_details']['discount_amount_currency']
                 for line in base_lines]
    assert sum(gross) == D('3.34')
    assert sorted(gross) == [D('1.11'), D('1.11'), D('1.12')]
    assert sum(discounts) == D('0.33')


def test_a_coarse_precision_is_corrected_to_the_document_total(
        company, currency):
    """Con dos decimales cada crudo de 1.0049 baja a 1.00 y suman 3.00,
    mientras el documento es 3.01: la tolerancia estricta reparte el delta
    hasta que la suma redondee al total."""
    base_lines = _rounded(
        _lines(currency, 3, price_unit=1.0049, quantity=1.0), company)
    AccountTax._round_raw_total_excluded(
        base_lines, company, precision_digits=2, apply_strict_tolerance=True)
    raw_sum = sum(line['tax_details']['raw_total_excluded_currency']
                  for line in base_lines)
    assert currency.round(raw_sum) == D('3.01')


def test_without_tolerance_only_the_raw_amounts_are_rounded(
        company, currency):
    base_lines = _rounded(
        _lines(currency, 3, price_unit=1.0049, quantity=1.0), company)
    AccountTax._round_raw_total_excluded(base_lines, company,
                                         precision_digits=2)
    assert [line['tax_details']['raw_total_excluded_currency']
            for line in base_lines] == [D('1.00')] * 3


def test_the_raw_tax_amounts_are_corrected_to_the_document_tax(
        company, currency):
    """Dos líneas de 12.12 × 12.12 con un 23 %: a dos decimales cada crudo
    sube a 33.79 (67.58), mientras el impuesto del documento es 67.57."""
    tax = AccountTax.objects.create(name='IVA 23', amount=D('23'),
                                    company=company)
    base_lines = _rounded(
        _lines(currency, 2, taxes=AccountTax.objects.filter(pk=tax.pk),
               price_unit=12.12, quantity=12.12),
        company)
    aggregated = AccountTax._aggregate_base_lines_tax_details(
        base_lines, lambda base_line, tax_data: True)
    AccountTax._round_raw_tax_amounts(
        aggregated, company, precision_digits=2, apply_strict_tolerance=True)
    raw_tax = sum(values[True]['raw_tax_amount_currency']
                  for _line, values in aggregated)
    assert currency.round(raw_tax) == D('67.57')
