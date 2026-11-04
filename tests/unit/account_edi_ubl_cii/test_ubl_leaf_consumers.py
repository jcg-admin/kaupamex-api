"""Los constructores UBL que sólo consumen la envoltura de ``account.tax``.

≙ ``_ubl_add_values_payable_rounding_amount`` (``odoo19c:
addons/account_edi_ubl_cii/models/account_edi_ubl.py:788-821``),
``_ubl_add_line_price_node`` (``:1098-1121``),
``_ubl_add_legal_monetary_total_payable_rounding_amount_node``
(``:2417-2445``) y ``AccountEdiXmlUBL20._add_document_line_total_vals``
(``account_edi_xml_ubl_20.py:906-925``), LGPL-3. Estaban bloqueados por la
envoltura de base-lines, que ya existe.
"""

import logging
from decimal import Decimal

import pytest

from addons.account.models import AccountTax
from addons.account_edi_ubl_cii.models.account_edi_ubl import AccountEdiUBL
from addons.account_edi_ubl_cii.models.account_edi_xml_ubl_20 import (
    AccountEdiXmlUBL20,
)
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
    return ResCompany.objects.create(code='hojas', name='Hojas',
                                     currency=currency)


def _lines(company, currency, *specs):
    lines = []
    for index, (taxes, values) in enumerate(specs, start=1):
        base_line = AccountTax._prepare_base_line_for_taxes_computation(
            {'id': index},
            tax_ids=AccountTax.objects.filter(pk__in=[t.pk for t in taxes]),
            currency_id=currency, rate=1.0, **values)
        AccountTax._add_tax_details_in_base_line(
            base_line, company, rounding_method='round_globally')
        lines.append(base_line)
    AccountTax._round_base_lines_tax_details(lines, company)
    return lines


def test_the_cash_rounding_lines_are_the_payable_rounding(
        company, currency, caplog):
    lines = _lines(
        company, currency,
        ([], {'price_unit': 100.0, 'quantity': 1.0}),
        ([], {'price_unit': 0.03, 'quantity': 1.0,
              'special_type': 'cash_rounding'}))
    vals = {'base_lines': lines, '_ubl_values': {}}
    with caplog.at_level(logging.WARNING):
        AccountEdiUBL._ubl_add_values_payable_rounding_amount(vals)
    ubl_values = vals['_ubl_values']
    assert ubl_values['payable_rounding_amount_currency'] == D('0.03')
    assert ubl_values['payable_rounding_amount'] == D('0.03')
    assert ubl_values['payable_rounding_base_lines'] == [lines[1]]
    assert 'DEPRECATED' in caplog.text


def test_the_line_price_is_the_gross_price_unit(company, currency):
    [base_line] = _lines(company, currency, (
        [], {'price_unit': 100.0, 'quantity': 2.0, 'discount': 10.0}))
    vals = {'line_node': {}, 'line_vals': {'base_line': base_line},
            'company': company}
    AccountEdiUBL._ubl_add_line_price_node(vals)
    price = vals['line_node']['cac:Price']['cbc:PriceAmount']
    assert str(price['_text']) == '100.0'
    assert price['currencyID'] == currency.name


@pytest.mark.parametrize('declared, expected', [
    (D('115.99'), '0.01'), (D('116.00'), None)])
def test_the_payable_rounding_closes_the_tax_inclusive_gap(
        company, currency, declared, expected):
    vat = AccountTax.objects.create(name='IVA 16', amount=D('16'),
                                    company=company)
    lines = _lines(company, currency,
                   ([vat], {'price_unit': 100.0, 'quantity': 1.0}))
    vals = {
        'base_lines': lines, 'currency_id': currency,
        'legal_monetary_total_node': {
            'cbc:TaxInclusiveAmount': {'_text': declared}},
    }
    AccountEdiUBL._ubl_add_legal_monetary_total_payable_rounding_amount_node(
        vals)
    node = vals['legal_monetary_total_node']['cbc:PayableRoundingAmount']
    rendered = str(node['_text']) if node['_text'] is not None else None
    assert rendered == expected


def test_the_line_total_adds_the_fixed_taxes(company, currency):
    deposit = AccountTax.objects.create(
        name='Envase', amount=D('0.50'), amount_type='fixed',
        company=company)
    vat = AccountTax.objects.create(name='IVA 16', amount=D('16'),
                                    company=company)
    [base_line] = _lines(company, currency, (
        [deposit, vat], {'price_unit': 10.0, 'quantity': 2.0}))
    vals = {
        'base_line': base_line,
        'fixed_taxes_as_allowance_charges': True,
        'total_grouping_function': lambda base_line, tax_data: True,
    }
    AccountEdiXmlUBL20._add_document_line_total_vals(vals)
    assert vals['total_fixed_taxes_currency'] == D('1.00')
    assert vals['total_excluded_currency'] == D('21.00')
    assert vals['total_excluded'] == D('21.00')
