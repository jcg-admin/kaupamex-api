"""El redondeo contractual de los detalles de impuestos de un documento.

≙ ``_round_tax_details_tax_amounts``, ``_round_tax_details_base_lines``,
``_round_tax_details_tax_amounts_from_tax_lines`` y
``_round_base_lines_tax_details`` (``odoo19c:
addons/account/models/account_tax.py:1895-2293``, LGPL-3). Los casos son los
ejemplos de los docstrings de la fuente:

- dos líneas de 21.53 con un 21 % incluido: la base del documento es 35.59
  (17.80 + 17.79) y el impuesto 7.47 (3.73 + 3.74), no 35.58 y 7.48;
- dos líneas de 12.12 × 12.12 con un 23 % excluido: el impuesto del
  documento es 67.57, no 2 × 33.79, y la base 293.79, no 2 × 146.89.

Con ``round_per_line`` el reparto no tiene delta que absorber: es el control
de que el redondeo global y no otra cosa produce la diferencia.
"""

from decimal import Decimal

import pytest

from addons.account.models import AccountTax
from addons.base.models import ResCompany
from addons.base.models.res_currency import ResCurrency

pytestmark = pytest.mark.django_db


@pytest.fixture
def currency(db):
    currency, _ = ResCurrency.objects.get_or_create(
        name='MXN', defaults={'symbol': '$'})
    return currency


@pytest.fixture
def company(db, currency):
    return ResCompany.objects.create(code='redondeo', name='Redondeo',
                                     currency=currency)


def _base_lines(tax, currency, count=2, **overrides):
    values = {
        'tax_ids': AccountTax.objects.filter(pk=tax.pk),
        'currency_id': currency, 'rate': 1.0, **overrides,
    }
    return [
        AccountTax._prepare_base_line_for_taxes_computation(
            {'id': index}, **values)
        for index in range(1, count + 1)
    ]


def _round(base_lines, company, method='round_globally', tax_lines=None):
    for base_line in base_lines:
        AccountTax._add_tax_details_in_base_line(
            base_line, company, rounding_method=method)
    AccountTax._round_base_lines_tax_details(base_lines, company,
                                             tax_lines=tax_lines)


def _untaxed(base_lines, suffix=''):
    return sum(
        line['tax_details'][f'total_excluded{suffix}']
        + line['tax_details'][f'delta_total_excluded{suffix}']
        for line in base_lines)


def _tax(base_lines, suffix=''):
    return sum(
        tax_data[f'tax_amount{suffix}']
        for line in base_lines
        for tax_data in line['tax_details']['taxes_data'])


@pytest.fixture
def included_tax(company):
    return AccountTax.objects.create(
        name='IVA 21 incluido', amount=Decimal('21'), price_include=True,
        company=company)


@pytest.fixture
def excluded_tax(company):
    return AccountTax.objects.create(
        name='IVA 23', amount=Decimal('23'), company=company)


def test_price_included_lines_reach_the_document_totals(
        company, currency, included_tax):
    base_lines = _base_lines(included_tax, currency, price_unit=21.53,
                             quantity=1.0)
    _round(base_lines, company)
    for suffix in ('', '_currency'):
        assert _untaxed(base_lines, suffix) == Decimal('35.59')
        assert _tax(base_lines, suffix) == Decimal('7.47')
        assert (_untaxed(base_lines, suffix) + _tax(base_lines, suffix)
                == Decimal('43.06'))
    totals = sorted(line['tax_details']['total_excluded']
                    for line in base_lines)
    assert totals == [Decimal('17.79'), Decimal('17.79')]
    taxes = sorted(tax_data['tax_amount'] for line in base_lines
                   for tax_data in line['tax_details']['taxes_data'])
    assert taxes == [Decimal('3.73'), Decimal('3.74')]


def test_price_excluded_lines_round_the_document_tax_and_base(
        company, currency, excluded_tax):
    base_lines = _base_lines(excluded_tax, currency, price_unit=12.12,
                             quantity=12.12)
    _round(base_lines, company)
    assert _tax(base_lines) == Decimal('67.57')
    assert _untaxed(base_lines) == Decimal('293.79')
    deltas = sorted(line['tax_details']['delta_total_excluded']
                    for line in base_lines)
    assert deltas == [Decimal('0'), Decimal('0.01')]


def test_round_per_line_leaves_no_delta(company, currency, excluded_tax):
    """Con ``round_per_line`` el motor redondea la base antes del impuesto
    (``odoo19c: :1237-1239``): 146.89 × 0.23 = 33.78 por línea, 67.56 en el
    documento, y no queda delta que repartir."""
    base_lines = _base_lines(excluded_tax, currency, price_unit=12.12,
                             quantity=12.12)
    _round(base_lines, company, method='round_per_line')
    assert _tax(base_lines) == Decimal('67.56')
    assert _untaxed(base_lines) == Decimal('293.78')
    assert all(not line['tax_details']['delta_total_excluded']
               for line in base_lines)


def test_total_included_adds_the_rounded_taxes(company, currency,
                                               excluded_tax):
    [base_line] = _base_lines(excluded_tax, currency, count=1,
                              price_unit=100.0, quantity=1.0)
    _round([base_line], company)
    details = base_line['tax_details']
    assert details['total_excluded'] == Decimal('100.00')
    assert details['total_included'] == Decimal('123.00')
    assert details['total_included_currency'] == Decimal('123.00')


def test_a_manual_tax_amount_replaces_the_computed_one(
        company, currency, excluded_tax):
    [base_line] = _base_lines(
        excluded_tax, currency, count=1, price_unit=100.0, quantity=1.0,
        manual_tax_amounts={str(excluded_tax.pk): {
            'tax_amount_currency': 22.5}})
    _round([base_line], company)
    [tax_data] = base_line['tax_details']['taxes_data']
    assert tax_data['tax_amount_currency'] == Decimal('22.50')
    assert tax_data['tax_amount'] == Decimal('22.50')


def test_existing_tax_lines_fix_the_tax_amount(company, currency,
                                               excluded_tax):
    """≙ ``_round_tax_details_tax_amounts_from_tax_lines`` (``:2105-2182``):
    el impuesto de los apuntes existentes gobierna, y la diferencia se
    reparte entre las líneas."""
    base_lines = _base_lines(excluded_tax, currency, price_unit=12.12,
                             quantity=12.12)
    repartition = excluded_tax.repartition_lines.filter(
        document_type='invoice', repartition_type='tax').first()
    if repartition is None:
        repartition = excluded_tax.repartition_lines.create(
            document_type='invoice', repartition_type='tax')
    tax_lines = [{
        'tax_repartition_line_id': repartition,
        'currency_id': currency,
        'sign': 1,
        'amount_currency': Decimal('67.60'),
        'balance': Decimal('67.60'),
    }]
    _round(base_lines, company, tax_lines=tax_lines)
    assert _tax(base_lines) == Decimal('67.60')
    assert _tax(base_lines, '_currency') == Decimal('67.60')


def test_without_tax_lines_the_tax_line_rounding_changes_nothing(
        company, currency, excluded_tax):
    base_lines = _base_lines(excluded_tax, currency, price_unit=12.12,
                             quantity=12.12)
    _round(base_lines, company, tax_lines=[])
    assert _tax(base_lines) == Decimal('67.57')
