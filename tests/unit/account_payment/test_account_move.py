"""Contrato de ``account_payment`` sobre ``account.move`` —
``transaction_ids``/``transaction_count``/``amount_paid`` (DEC-SALE-01, vía
``AccountMoveTransactionLink``). Ver el docstring de
``src/addons/account_payment/models/account_move.py`` para lo NO portado
(``authorized_transaction_ids``/``payment_action_capture``/``payment_
action_void`` — ``payment.Payment`` no tiene estado ``authorized``).

Portación de ``odoo19c: account_payment/models/account_move.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``).
"""
from datetime import date
from decimal import Decimal

import pytest

from addons.account.models import AccountJournal, AccountMove
from addons.account_payment.models.account_move import (
    apply_account_payment_extensions as apply_account_payment_,
)
from addons.account_payment.models.links import AccountMoveTransactionLink
from addons.base.models import ResCompany
from addons.payment.models import Payment
from addons.sale.models import SaleOrder

pytestmark = pytest.mark.django_db

apply_account_payment_()


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme-am', name='ACME AM')


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(
        name='Ventas', code='VENAM', type='sale', company=company)


@pytest.fixture
def move(company, journal):
    return AccountMove.objects.create(
        journal=journal, company=company, date=date(2026, 1, 1),
        move_type='out_invoice',
    )


@pytest.fixture
def sale_order():
    return SaleOrder.objects.create()


def _payment(sale_order, amount, status):
    return Payment.objects.create(
        sale_order=sale_order, gateway=Payment.GATEWAY_MERCADOPAGO,
        amount=amount, status=status,
    )


class TestTransactionIds:
    def test_empty_without_links(self, move):
        assert list(move.transaction_ids) == []

    def test_returns_linked_transactions(self, move, sale_order):
        tx = _payment(sale_order, Decimal('100.00'), Payment.STATUS_APPROVED)
        AccountMoveTransactionLink.objects.create(move=move, transaction=tx)
        assert list(move.transaction_ids) == [tx]

    def test_two_invoices_can_share_a_transaction(self, move, sale_order, company, journal):
        other_move = AccountMove.objects.create(
            journal=journal, company=company, date=date(2026, 1, 2),
            move_type='out_invoice',
        )
        tx = _payment(sale_order, Decimal('300.00'), Payment.STATUS_APPROVED)
        AccountMoveTransactionLink.objects.create(move=move, transaction=tx)
        AccountMoveTransactionLink.objects.create(move=other_move, transaction=tx)
        assert list(move.transaction_ids) == [tx]
        assert list(other_move.transaction_ids) == [tx]


class TestTransactionCount:
    def test_zero_without_links(self, move):
        assert move.transaction_count == 0

    def test_counts_all_links(self, move, sale_order):
        tx1 = _payment(sale_order, Decimal('10.00'), Payment.STATUS_FAILED)
        tx2 = _payment(sale_order, Decimal('10.00'), Payment.STATUS_APPROVED)
        AccountMoveTransactionLink.objects.create(move=move, transaction=tx1)
        AccountMoveTransactionLink.objects.create(move=move, transaction=tx2)
        assert move.transaction_count == 2


class TestAmountPaid:
    def test_zero_without_transactions(self, move):
        assert move.amount_paid == Decimal('0.00')

    def test_sums_only_approved(self, move, sale_order):
        approved = _payment(sale_order, Decimal('75.50'), Payment.STATUS_APPROVED)
        failed = _payment(sale_order, Decimal('999.00'), Payment.STATUS_FAILED)
        pending = _payment(sale_order, Decimal('50.00'), Payment.STATUS_PENDING)
        for tx in (approved, failed, pending):
            AccountMoveTransactionLink.objects.create(move=move, transaction=tx)
        assert move.amount_paid == Decimal('75.50')

    def test_sums_multiple_approved(self, move, sale_order):
        tx1 = _payment(sale_order, Decimal('30.00'), Payment.STATUS_APPROVED)
        tx2 = _payment(sale_order, Decimal('20.00'), Payment.STATUS_APPROVED)
        AccountMoveTransactionLink.objects.create(move=move, transaction=tx1)
        AccountMoveTransactionLink.objects.create(move=move, transaction=tx2)
        assert move.amount_paid == Decimal('50.00')
