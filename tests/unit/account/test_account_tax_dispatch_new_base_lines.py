"""Sacar impuestos de una base-line a sub-líneas y volver a agregarlas.

≙ ``_partition_base_lines_taxes`` (``:3885-3913``), ``_merge_tax_details``
(``:3149-3197``), ``_split_tax_data`` (``:3246-3295``),
``_reduce_base_lines_with_grouping_function`` (``:3462-3549``),
``_dispatch_taxes_into_new_base_lines`` (``:4049-4205``) y
``_turn_removed_taxes_into_new_base_lines`` (``:4207-4230``) de ``odoo19c:
addons/account/models/account_tax.py`` (LGPL-3). El EDI los usa para informar
una retención como línea propia.

Los casos: una línea de 100 con un 16 % y una retención del 10 %; y una de 100
con un impuesto que se suma a la base (10 %) seguido de un 16 % afectado, donde
sacar el primero obliga a partir el segundo: 16.00 queda en la línea y 1.60
viaja con la sub-línea.
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
    return ResCompany.objects.create(code='reparte', name='Reparte',
                                     currency=currency)


@pytest.fixture
def vat(company):
    return AccountTax.objects.create(name='IVA 16', amount=D('16'),
                                     company=company)


@pytest.fixture
def withholding(company):
    return AccountTax.objects.create(name='Retención 10', amount=D('-10'),
                                     company=company)


def _line(company, currency, taxes, index=1, price_unit=100.0):
    base_line = AccountTax._prepare_base_line_for_taxes_computation(
        {'id': index},
        tax_ids=AccountTax.objects.filter(pk__in=[t.pk for t in taxes]),
        currency_id=currency, rate=1.0, price_unit=price_unit, quantity=1.0)
    AccountTax._add_tax_details_in_base_line(
        base_line, company, rounding_method='round_globally')
    AccountTax._round_base_lines_tax_details([base_line], company)
    return base_line


def _is_withholding(base_line, tax_data):
    return tax_data['tax'].amount < 0


def test_the_partition_separates_kept_and_excluded_taxes(
        company, currency, vat, withholding):
    base_line = _line(company, currency, [vat, withholding])
    [(line, keep, exclude)], found = AccountTax._partition_base_lines_taxes(
        [base_line], lambda line, tax_data: tax_data['tax'].amount > 0)
    assert line is base_line
    assert list(keep) == [vat]
    assert list(exclude) == [withholding]
    assert found is True


def test_the_withholding_becomes_its_own_sub_line(
        company, currency, vat, withholding):
    [line] = AccountTax._dispatch_taxes_into_new_base_lines(
        [_line(company, currency, [vat, withholding])], company,
        _is_withholding)
    assert [d['tax'] for d in line['tax_details']['taxes_data']] == [vat]
    assert line['tax_details']['total_included_currency'] == D('116.00')
    [removed] = line['removed_taxes_data_base_lines']
    assert removed['tax_details']['total_excluded_currency'] == D('-10.00')
    assert removed['price_unit'] == D('-10.00')
    assert removed['_removed_tax_data']['tax'] == withholding


def test_a_line_without_excluded_taxes_is_kept_whole(company, currency, vat):
    [line] = AccountTax._dispatch_taxes_into_new_base_lines(
        [_line(company, currency, [vat])], company, _is_withholding)
    assert line['removed_taxes_data_base_lines'] == []
    assert line['tax_details']['total_included_currency'] == D('116.00')


def test_removing_a_base_affecting_tax_splits_the_affected_one(
        company, currency):
    excise = AccountTax.objects.create(
        name='Especial 10', amount=D('10'), include_base_amount=True,
        sequence=1, company=company)
    vat = AccountTax.objects.create(
        name='IVA 16', amount=D('16'), is_base_affected=True, sequence=2,
        company=company)
    base_line = _line(company, currency, [excise, vat])
    [line] = AccountTax._dispatch_taxes_into_new_base_lines(
        [base_line], company,
        lambda base_line, tax_data: tax_data['tax'] == excise)
    [kept_vat] = line['tax_details']['taxes_data']
    assert kept_vat['tax'] == vat
    assert kept_vat['tax_amount_currency'] == D('16.00')
    [removed] = line['removed_taxes_data_base_lines']
    [moved_vat] = removed['tax_details']['taxes_data']
    assert moved_vat['tax_amount_currency'] == D('1.60')
    assert removed['tax_details']['total_included_currency'] == D('11.60')


def test_the_split_keeps_every_cent(company, currency, vat):
    [tax_data] = _line(company, currency, [vat])['tax_details']['taxes_data']
    pieces = AccountTax._split_tax_data(
        {'currency_id': currency}, tax_data, company,
        [{'factor': D('1')}, {'factor': D('2')}])
    assert sum(p['tax_amount_currency'] for p in pieces) == D('16.00')
    assert sorted(p['tax_amount_currency'] for p in pieces) == [
        D('5.33'), D('10.67')]


def test_merging_two_details_adds_their_amounts(company, currency, vat):
    first = _line(company, currency, [vat])['tax_details']
    second = _line(company, currency, [vat], price_unit=50.0)['tax_details']
    merged = AccountTax._merge_tax_details(first, second)
    assert merged['total_excluded_currency'] == D('150.00')
    [tax_data] = merged['taxes_data']
    assert tax_data['tax_amount_currency'] == D('24.00')


def test_the_removed_sub_lines_are_aggregated_by_tax(
        company, currency, vat, withholding):
    lines = AccountTax._dispatch_taxes_into_new_base_lines(
        [_line(company, currency, [vat, withholding], index=i)
         for i in (1, 2)],
        company, _is_withholding)
    [aggregated] = AccountTax._turn_removed_taxes_into_new_base_lines(
        lines, company)
    assert aggregated['price_unit'] == D('-20.00')
    assert aggregated['tax_details']['total_excluded_currency'] == D('-20.00')
