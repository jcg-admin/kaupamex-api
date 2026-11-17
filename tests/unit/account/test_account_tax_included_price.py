"""Los tres helpers de precio con impuesto incluido de ``account.tax``.

≙ ``odoo19c: addons/account/models/account_tax.py:5078-5108``.
"""
from decimal import Decimal

import pytest

from addons.account.models import AccountTax
from addons.base.models import ResCompany

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def parent():
    return ResCompany.objects.create(code='madre', name='Madre')


@pytest.fixture
def child(parent):
    return ResCompany.objects.create(code='hija', name='Hija', parent=parent)


def _tax(company, name, amount, **values):
    return AccountTax.objects.create(
        name=name, amount=Decimal(amount), company=company, **values)


def _set(*taxes):
    return AccountTax.objects.filter(pk__in=[t.pk for t in taxes])


def test_the_company_own_taxes_win(parent, child):
    own = _tax(child, 'Hija 16', '16')
    _tax(parent, 'Madre 16', '16')
    taxes = _set(*AccountTax.objects.filter(company__in=[parent, child]))
    assert list(taxes._filter_taxes_by_company(child)) == [own]


def test_without_own_taxes_the_parent_ones_are_used(parent, child):
    inherited = _tax(parent, 'Madre 8', '8')
    assert list(_set(inherited)._filter_taxes_by_company(child)) == [inherited]


def test_no_tax_in_the_hierarchy_gives_an_empty_set(parent, child):
    other = ResCompany.objects.create(code='otra', name='Otra')
    foreign = _tax(other, 'Otra 16', '16')
    assert not _set(foreign)._filter_taxes_by_company(child).exists()


def test_an_empty_set_is_returned_as_is(child):
    empty = AccountTax.objects.none()
    assert empty._filter_taxes_by_company(child) is empty


def test_an_included_tax_missing_on_the_line_is_removed(child):
    included = _tax(child, 'IVA incl', '16', price_include=True)
    assert AccountTax._fix_tax_included_price(
        Decimal('116'), _set(included), AccountTax.objects.none(),
    ) == Decimal('100.00')


def test_an_included_tax_kept_on_the_line_leaves_the_price(child):
    included = _tax(child, 'IVA incl', '16', price_include=True)
    assert AccountTax._fix_tax_included_price(
        Decimal('116'), _set(included), _set(included)) == Decimal('116')


def test_an_excluded_tax_never_changes_the_price(child):
    excluded = _tax(child, 'IVA', '16')
    assert AccountTax._fix_tax_included_price(
        Decimal('116'), _set(excluded), AccountTax.objects.none(),
    ) == Decimal('116')


def test_the_company_variant_only_compares_that_company(parent, child):
    other_company = _tax(parent, 'Madre incl', '16', price_include=True)
    assert AccountTax._fix_tax_included_price_company(
        Decimal('116'), _set(other_company), AccountTax.objects.none(), child,
    ) == Decimal('116')
    assert AccountTax._fix_tax_included_price_company(
        Decimal('116'), _set(other_company), AccountTax.objects.none(), None,
    ) == Decimal('100.00')
