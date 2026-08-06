"""Contrato de extractos y candados — portación fiel de Odoo ``account`` (19c).

Cubre:

- ``AccountCashRounding``: ``round()``/``compute_difference()`` (Odoo
  ``round``/``compute_difference``, estrategias UP/DOWN/HALF-UP).
- ``AccountIncoterms``: creación + ``__str__`` (Odoo ``_compute_display_name``).
- ``AccountJournalGroup``: único ``(company, name)`` (Odoo ``_uniq_name``).
- ``AccountLockException``: ``state`` derivado (active/revoked/expired) y
  ``applies_to()`` (sustituto de los computados ``*_lock_date`` de la
  referencia — ver docstring de ``account_lock_exception.py``).
- ``AccountBankStatement``/``AccountBankStatementLine``: ``_inherits`` de
  ``account.move`` (delegación por propiedad) y ``recompute()``.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from addons.account.models import (
    AccountBankStatement,
    AccountBankStatementLine,
    AccountCashRounding,
    AccountIncoterms,
    AccountJournal,
    AccountJournalGroup,
    AccountLockException,
    AccountMove,
)
from addons.base.models import ResCompany

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(
        name='Banco', code='BNK', type='bank', company=company)


class TestAccountCashRounding:
    def test_round_half_up(self, company):
        profile = AccountCashRounding.objects.create(
            name='CHF 0.05', rounding=Decimal('0.05'),
            rounding_method=AccountCashRounding.METHOD_HALF_UP)
        assert profile.round(Decimal('23.93')) == Decimal('23.95')

    def test_round_down(self, company):
        profile = AccountCashRounding.objects.create(
            name='Down', rounding=Decimal('0.05'),
            rounding_method=AccountCashRounding.METHOD_DOWN)
        assert profile.round(Decimal('23.94')) == Decimal('23.90')

    def test_compute_difference(self, company):
        profile = AccountCashRounding.objects.create(
            name='CHF 0.05', rounding=Decimal('0.05'),
            rounding_method=AccountCashRounding.METHOD_HALF_UP)
        # Odoo docstring: base_amount=23.91, redondeado=23.90 -> diff=-0.01
        assert profile.compute_difference(Decimal('23.91')) == Decimal('-0.01')


class TestAccountIncoterms:
    def test_create_and_str(self):
        term = AccountIncoterms.objects.create(name='Free on Board', code='FOB')
        assert str(term) == '[FOB] Free on Board'


class TestAccountJournalGroup:
    def test_unique_name_per_company(self, company):
        AccountJournalGroup.objects.create(name='Grupo A', company=company)
        with transaction.atomic(), pytest.raises(IntegrityError):
            AccountJournalGroup.objects.create(name='Grupo A', company=company)


class TestAccountLockException:
    def test_state_active_by_default(self, company):
        exc = AccountLockException.objects.create(
            company=company, lock_date_field='sale_lock_date')
        assert exc.state == AccountLockException.STATE_ACTIVE

    def test_state_revoked_after_revoke(self, company):
        exc = AccountLockException.objects.create(
            company=company, lock_date_field='sale_lock_date')
        exc.revoke()
        assert exc.state == AccountLockException.STATE_REVOKED

    def test_state_expired_past_end_datetime(self, company):
        exc = AccountLockException.objects.create(
            company=company, lock_date_field='sale_lock_date',
            end_datetime=timezone.now() - timedelta(days=1))
        assert exc.state == AccountLockException.STATE_EXPIRED

    def test_applies_to_matching_field(self, company):
        exc = AccountLockException.objects.create(
            company=company, lock_date_field='purchase_lock_date',
            lock_date='2026-01-01')
        assert exc.applies_to('purchase_lock_date') == exc.lock_date
        assert exc.applies_to('sale_lock_date') is None


class TestAccountBankStatement:
    def test_line_delegates_to_move(self, company, journal):
        move = AccountMove.objects.create(
            company=company, journal=journal, date='2026-01-15')
        line = AccountBankStatementLine.objects.create(
            move=move, amount=Decimal('150.00'), payment_ref='Depósito')
        assert line.journal == journal
        assert line.company == company
        assert line.date == move.date
        assert line.state == 'draft'

    def test_recompute_balance_and_completeness(self, company, journal):
        move = AccountMove.objects.create(
            company=company, journal=journal, date='2026-01-15', state='posted')
        statement = AccountBankStatement.objects.create(
            company=company, journal=journal,
            balance_start=Decimal('100.00'), balance_end_real=Decimal('250.00'))
        AccountBankStatementLine.objects.create(
            move=move, statement=statement, amount=Decimal('150.00'))
        statement.recompute()
        assert statement.balance_end == Decimal('250.00')
        assert statement.is_complete is True
