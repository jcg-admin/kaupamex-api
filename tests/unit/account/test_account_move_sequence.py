"""RED→GREEN — ``AccountMove.post()`` asigna secuencia de ``name``.

Rebanada 4 (d) de H-API-08: gap destapado por la rebanada 2 — ``post()`` dejaba
``name='/'`` a diferencia de Odoo, que asigna una secuencia por diario/tipo/año
al publicar (``INV/2026/00001``). Se porta la mecánica mínima: ``name`` con la
forma ``{prefijo}/{código-diario}/{año}/{consecutivo}``, único por
(diario, move_type, año). Análogo a Odoo ``account.move._get_last_sequence`` /
``_set_next_sequence``.
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.account.models import (
    AccountAccount,
    AccountJournal,
    AccountMove,
    AccountMoveLine,
)
from addons.base.models import ResCompany


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.fixture
def setup(db, company):
    journal = AccountJournal.objects.create(
        name='Ventas', code='VEN', type='sale', company=company)
    receivable = AccountAccount.objects.create(
        code='105', name='Clientes', account_type='asset_receivable',
        company=company)
    income = AccountAccount.objects.create(
        code='401', name='Ventas', account_type='income', company=company)
    return company, journal, receivable, income


def _balanced(company, journal, receivable, income,
              move_type='out_invoice', amount=Decimal('100.00')):
    move = AccountMove.objects.create(
        move_type=move_type, date=timezone.now().date(),
        journal=journal, company=company)
    AccountMoveLine.objects.create(move=move, account=receivable, debit=amount)
    AccountMoveLine.objects.create(move=move, account=income, credit=amount)
    return move


@pytest.mark.django_db
class TestAccountMoveSequence:
    def test_first_invoice_gets_sequence(self, setup):
        move = _balanced(*setup)
        move.post()
        move.refresh_from_db()
        assert move.name == f'INV/VEN/{move.date.year}/00001'

    def test_sequence_increments_per_journal(self, setup):
        first = _balanced(*setup)
        first.post()
        second = _balanced(*setup)
        second.post()
        first.refresh_from_db()
        second.refresh_from_db()
        assert first.name.endswith('/00001')
        assert second.name.endswith('/00002')

    def test_refund_has_own_sequence(self, setup):
        invoice = _balanced(*setup)
        invoice.post()
        refund = _balanced(*setup, move_type='out_refund')
        refund.post()
        refund.refresh_from_db()
        assert refund.name == f'RINV/VEN/{refund.date.year}/00001'

    def test_existing_name_is_preserved(self, setup):
        move = _balanced(*setup)
        move.name = 'MANUAL-001'
        move.save()
        move.post()
        move.refresh_from_db()
        assert move.name == 'MANUAL-001'
