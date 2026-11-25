"""Las ramas previas de ``account.account.write``.

≙ ``odoo19c: addons/account/models/account_account.py:1053-1066``: la moneda
no puede contradecir una divisa extranjera ya asentada, una cuenta usada en
un reparto de impuestos no se depreca y ``reconcile`` no se desactiva con
conciliaciones parciales pendientes
(``designs/account-account-write-branches.md``).
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.account.models import (
    AccountJournal,
    AccountMove,
    AccountMoveLine,
    AccountPartialReconcile,
    AccountTax,
    AccountTaxRepartitionLine,
)
from addons.base.models import ResCompany, ResCurrency
from exceptions import UserError
from orm.commands import Command
from orm.environments import company_scope, env as current_env, sudo

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def company():
    return ResCompany.objects.create(
        code='kaupamex_test_write_branches', name='Ramas')


@pytest.fixture(autouse=True)
def _active_company(company):
    with company_scope(company.pk):
        yield


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(
        name='Varios', code='MISC-W', type='general', company=company)


@pytest.fixture
def account(company):
    return current_env()['account.account'].sudo().create({
        'code': '102000', 'name': 'Bancos', 'account_type': 'asset_cash',
        'company_ids': [Command.set([company.pk])],
    })


def _currency(name):
    return ResCurrency.objects.get_or_create(
        name=name, defaults={'symbol': name})[0]


def _line(account, journal, company, currency=None,
          debit=Decimal('0.00'), credit=Decimal('0.00')):
    move = AccountMove.objects.create(
        date=timezone.now().date(), journal=journal, company=company)
    return AccountMoveLine.objects.create(
        move=move, account=account, currency=currency,
        debit=debit, credit=credit)


def test_a_currency_contradicting_a_posted_one_is_refused(
        account, journal, company):
    _line(account, journal, company, currency=_currency('USD'),
          debit=Decimal('10.00'))
    with pytest.raises(UserError, match='different foreign currency'):
        account.write({'currency': _currency('EUR').pk})


def test_a_currency_matching_the_posted_ones_is_kept(
        account, journal, company):
    usd = _currency('USD')
    _line(account, journal, company, currency=usd, debit=Decimal('10.00'))
    _line(account, journal, company, debit=Decimal('5.00'))
    account.write({'currency': usd.pk})


def test_an_account_in_a_tax_distribution_cannot_be_deprecated(
        account, company):
    tax = AccountTax.objects.create(name='IVA 16', company=company)
    AccountTaxRepartitionLine.objects.create(
        tax=tax, document_type='invoice', repartition_type='tax',
        account=account)
    with pytest.raises(UserError, match='tax distribution'):
        account.write({'deprecated': True})


def test_an_unused_account_can_be_deprecated(account):
    account.write({'deprecated': True})


def test_reconcile_stays_on_with_pending_partials(account, journal, company):
    account.write({'reconcile': True})
    debit = _line(account, journal, company, debit=Decimal('100.00'))
    credit = _line(account, journal, company, credit=Decimal('60.00'))
    AccountPartialReconcile.create_partial(debit, credit, Decimal('60.00'))
    with pytest.raises(UserError, match='partial reconciliations'):
        account.write({'reconcile': False})


def test_reconcile_turns_off_without_partials(account):
    account.write({'reconcile': True})
    account.write({'reconcile': False})
