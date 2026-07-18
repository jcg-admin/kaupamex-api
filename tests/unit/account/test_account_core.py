"""Contrato del núcleo ``account`` — portación fiel del libro mayor de doble
entrada de Odoo (``account``, 18/19).

Cubre cada modelo del paquete:

- ``AccountAccount``: ``internal_group`` derivado de ``account_type`` (Odoo
  ``_compute_internal_group``); ``account_type`` incluye el drift 19
  (``expense_other``, H-ACC-01); único ``(company, code)``.
- ``AccountJournal``: ``type`` enum; único ``(company, code)``.
- ``AccountTax.compute_amount``: percent/fixed/division (Odoo ``_compute_amount``).
- ``AccountMove.post``: invariante de doble entrada (Odoo ``_check_balanced``).
- ``AccountMoveLine``: ``balance = debit - credit`` (Odoo ``_compute_balance``).
- ``AccountPayment``: enums payment_type/partner_type/state.
"""
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from exceptions import UserError
from addons.account.models import (
    AccountAccount,
    AccountJournal,
    AccountMove,
    AccountMoveLine,
    AccountPayment,
    AccountTax,
)
from addons.company.models import Company

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    return Company.objects.create(code='acme', name='ACME')


class TestAccountAccount:
    @pytest.mark.parametrize('atype,group', [
        ('asset_receivable', 'asset'),
        ('liability_payable', 'liability'),
        ('equity_unaffected', 'equity'),
        ('income', 'income'),
        ('expense_direct_cost', 'expense'),
        ('off_balance', 'off'),
    ])
    def test_internal_group_derived_from_type(self, company, atype, group):
        acc = AccountAccount.objects.create(
            code='100', name='X', account_type=atype, company=company)
        assert acc.internal_group == group

    def test_expense_other_is_valid_type_19_drift(self, company):
        # H-ACC-01: 19 añade expense_other; se adopta el superset.
        acc = AccountAccount.objects.create(
            code='600', name='Otros gastos', account_type='expense_other',
            company=company)
        assert acc.internal_group == 'expense'

    def test_unique_code_per_company(self, company):
        AccountAccount.objects.create(
            code='100', name='A', account_type='asset_cash', company=company)
        with transaction.atomic(), pytest.raises(IntegrityError):
            AccountAccount.objects.create(
                code='100', name='B', account_type='asset_cash', company=company)


class TestAccountJournal:
    def test_type_choices(self, company):
        j = AccountJournal.objects.create(
            name='Ventas', code='VEN', type='sale', company=company)
        assert j.type == 'sale'

    def test_unique_code_per_company(self, company):
        AccountJournal.objects.create(
            name='Ventas', code='VEN', type='sale', company=company)
        with transaction.atomic(), pytest.raises(IntegrityError):
            AccountJournal.objects.create(
                name='Otro', code='VEN', type='general', company=company)


class TestAccountTax:
    def test_percent(self, company):
        tax = AccountTax.objects.create(
            name='IVA 16', amount=Decimal('16'), amount_type='percent',
            company=company)
        assert tax.compute_amount(Decimal('100')) == Decimal('16')

    def test_fixed(self, company):
        tax = AccountTax.objects.create(
            name='Cuota', amount=Decimal('5'), amount_type='fixed',
            company=company)
        assert tax.compute_amount(Decimal('100')) == Decimal('5')

    def test_division_included(self, company):
        # 116 con IVA incluido 16% → impuesto = 116 - 116/1.16 = 16.
        tax = AccountTax.objects.create(
            name='IVA incl', amount=Decimal('16'), amount_type='division',
            company=company)
        result = tax.compute_amount(Decimal('116'))
        assert result == pytest.approx(Decimal('16'), abs=Decimal('0.0001'))


class TestAccountMoveLine:
    def _move(self, company):
        j = AccountJournal.objects.create(
            name='Varios', code='MISC', type='general', company=company)
        return AccountMove.objects.create(
            date=timezone.now().date(), journal=j, company=company)

    def test_balance_computed_from_debit_credit(self, company):
        move = self._move(company)
        line = AccountMoveLine.objects.create(
            move=move, debit=Decimal('30.00'), credit=Decimal('0.00'))
        assert line.balance == Decimal('30.00')
        line2 = AccountMoveLine.objects.create(
            move=move, debit=Decimal('0.00'), credit=Decimal('12.50'))
        assert line2.balance == Decimal('-12.50')


class TestAccountMovePost:
    def _fixture(self, company):
        j = AccountJournal.objects.create(
            name='Varios', code='MISC', type='general', company=company)
        cash = AccountAccount.objects.create(
            code='101', name='Caja', account_type='asset_cash', company=company)
        income = AccountAccount.objects.create(
            code='401', name='Ventas', account_type='income', company=company)
        move = AccountMove.objects.create(
            date=timezone.now().date(), journal=j, company=company)
        return move, cash, income

    def test_post_balanced_move(self, company):
        move, cash, income = self._fixture(company)
        AccountMoveLine.objects.create(move=move, account=cash, debit=Decimal('100.00'))
        AccountMoveLine.objects.create(move=move, account=income, credit=Decimal('100.00'))
        assert move.is_balanced() is True
        move.post()
        move.refresh_from_db()
        assert move.state == 'posted'
        assert move.amount_total == Decimal('100.00')

    def test_post_unbalanced_rejected(self, company):
        move, cash, income = self._fixture(company)
        AccountMoveLine.objects.create(move=move, account=cash, debit=Decimal('100.00'))
        AccountMoveLine.objects.create(move=move, account=income, credit=Decimal('90.00'))
        with pytest.raises(UserError):
            move.post()
        move.refresh_from_db()
        assert move.state == 'draft'

    def test_post_empty_move_rejected(self, company):
        move, _, _ = self._fixture(company)
        with pytest.raises(UserError):
            move.post()

    def test_button_cancel(self, company):
        move, cash, income = self._fixture(company)
        move.button_cancel()
        move.refresh_from_db()
        assert move.state == 'cancel'


class TestAccountPayment:
    def test_defaults(self, company):
        j = AccountJournal.objects.create(
            name='Banco', code='BNK', type='bank', company=company)
        p = AccountPayment.objects.create(
            amount=Decimal('250.00'), journal=j, company=company)
        assert p.payment_type == 'inbound'
        assert p.partner_type == 'customer'
        assert p.state == 'draft'
        assert p.is_reconciled is False
