"""Contrato de ``AccountDebitNoteWizard`` — ≙ ``account.debit.note``.

Portación fiel de ``odoo19c: addons/account_debit_note/wizard/
account_debit_note.py`` (``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``).
``TransientModel`` sin tabla — el estado del wizard lo pasa el llamador como
argumentos (ver el docstring del módulo portado).

Requiere ``addons.account_debit_note`` en ``INSTALLED_APPS`` (fuera del
alcance de este porte — ver ``apps.py``) para que la migración cree la tabla
de ``AccountMoveDebitNote`` (el wizard mismo no tiene tabla — ``managed =
False``).
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.account.models import AccountAccount, AccountJournal, AccountMove, AccountMoveLine
from addons.account_debit_note.models.account_move import AccountMoveDebitNote
from addons.account_debit_note.wizard.account_debit_note import AccountDebitNoteWizard
from addons.base.models import ResCompany
from exceptions import UserError

pytestmark = pytest.mark.django_db


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(
        name='Ventas', code='VEN', type='sale', company=company)


@pytest.fixture
def accounts(company):
    receivable = AccountAccount.objects.create(
        code='105', name='Clientes', account_type='asset_receivable', company=company)
    income = AccountAccount.objects.create(
        code='401', name='Ventas', account_type='income', company=company)
    return receivable, income


def _posted_move(company, journal, accounts, move_type='out_invoice',
                  amount=Decimal('100.00')):
    receivable, income = accounts
    move = AccountMove.objects.create(
        move_type=move_type, date=timezone.now().date(),
        journal=journal, company=company, state='posted')
    AccountMoveLine.objects.create(move=move, account=receivable, debit=amount)
    AccountMoveLine.objects.create(move=move, account=income, credit=amount)
    return move


class TestValidateMoves:
    def test_unposted_move_raises_usererror(self, company, journal, accounts):
        receivable, income = accounts
        draft = AccountMove.objects.create(
            move_type='out_invoice', date=timezone.now().date(),
            journal=journal, company=company)
        with pytest.raises(UserError):
            AccountDebitNoteWizard.validate_moves([draft])

    def test_move_already_a_debit_note_raises_usererror(
            self, company, journal, accounts):
        origin = _posted_move(company, journal, accounts)
        debit_note = _posted_move(company, journal, accounts)
        AccountMoveDebitNote.objects.create(move=debit_note, origin=origin)
        with pytest.raises(UserError):
            AccountDebitNoteWizard.validate_moves([debit_note])

    def test_non_invoiceable_type_raises_usererror(self, company, journal, accounts):
        entry = _posted_move(company, journal, accounts, move_type='entry')
        with pytest.raises(UserError):
            AccountDebitNoteWizard.validate_moves([entry])

    def test_valid_move_passes(self, company, journal, accounts):
        move = _posted_move(company, journal, accounts)
        assert AccountDebitNoteWizard.validate_moves([move]) == [move]

    def test_the_four_allowed_types_pass(self, company, journal, accounts):
        for move_type in AccountDebitNoteWizard.ALLOWED_MOVE_TYPES:
            move = _posted_move(company, journal, accounts, move_type=move_type)
            AccountDebitNoteWizard.validate_moves([move])   # no debe levantar


class TestPrepareDefaultValues:
    def test_ref_includes_the_reason(self, company, journal, accounts):
        move = _posted_move(company, journal, accounts)
        values = AccountDebitNoteWizard.prepare_default_values(
            move, reason='ajuste de precio')
        assert values['ref'] == f'{move.name}, ajuste de precio'

    def test_ref_without_reason_is_the_moves_name(self, company, journal, accounts):
        move = _posted_move(company, journal, accounts)
        values = AccountDebitNoteWizard.prepare_default_values(move)
        assert values['ref'] == move.name

    def test_out_refund_switches_type(self, company, journal, accounts):
        refund = _posted_move(company, journal, accounts, move_type='out_refund')
        values = AccountDebitNoteWizard.prepare_default_values(refund)
        assert values['move_type'] == 'out_invoice'

    def test_in_refund_becomes_in_invoice(self, company, journal, accounts):
        refund = _posted_move(company, journal, accounts, move_type='in_refund')
        values = AccountDebitNoteWizard.prepare_default_values(refund)
        assert values['move_type'] == 'in_invoice'

    def test_invoice_keeps_its_type(self, company, journal, accounts):
        move = _posted_move(company, journal, accounts, move_type='out_invoice')
        values = AccountDebitNoteWizard.prepare_default_values(move)
        assert values['move_type'] == 'out_invoice'

    def test_date_defaults_to_the_moves_date(self, company, journal, accounts):
        move = _posted_move(company, journal, accounts)
        values = AccountDebitNoteWizard.prepare_default_values(move)
        assert values['date'] == move.date

    def test_explicit_date_takes_priority(self, company, journal, accounts):
        move = _posted_move(company, journal, accounts)
        other_date = timezone.now().date().replace(day=1)
        values = AccountDebitNoteWizard.prepare_default_values(move, date=other_date)
        assert values['date'] == other_date

    def test_journal_defaults_to_the_moves_journal(self, company, journal, accounts):
        move = _posted_move(company, journal, accounts)
        values = AccountDebitNoteWizard.prepare_default_values(move)
        assert values['journal'] == journal

    def test_explicit_journal_takes_priority(self, company, journal, accounts):
        move = _posted_move(company, journal, accounts)
        other_journal = AccountJournal.objects.create(
            name='Compras', code='COM', type='purchase', company=company)
        values = AccountDebitNoteWizard.prepare_default_values(move, journal=other_journal)
        assert values['journal'] == other_journal

    def test_copies_company_and_currency(self, company, journal, accounts):
        move = _posted_move(company, journal, accounts)
        values = AccountDebitNoteWizard.prepare_default_values(move)
        assert values['company'] == move.company
        assert values['currency'] == move.currency


class TestCreateDebit:
    def test_creates_one_debit_note_per_move(self, company, journal, accounts):
        origin_1 = _posted_move(company, journal, accounts)
        origin_2 = _posted_move(company, journal, accounts)
        debit_notes = AccountDebitNoteWizard.create_debit([origin_1, origin_2])
        assert len(debit_notes) == 2

    def test_the_debit_note_is_linked_to_the_origin(self, company, journal, accounts):
        origin = _posted_move(company, journal, accounts)
        [debit_note] = AccountDebitNoteWizard.create_debit([origin])
        assert AccountMoveDebitNote.origin_for(debit_note) == origin

    def test_the_debit_note_is_born_in_draft(self, company, journal, accounts):
        origin = _posted_move(company, journal, accounts)
        [debit_note] = AccountDebitNoteWizard.create_debit([origin])
        assert debit_note.state == 'draft'
        assert debit_note.name == '/'

    def test_without_copy_lines_the_debit_note_has_no_lines(
            self, company, journal, accounts):
        origin = _posted_move(company, journal, accounts)
        [debit_note] = AccountDebitNoteWizard.create_debit([origin], copy_lines=False)
        assert debit_note.line_ids.count() == 0

    def test_with_copy_lines_the_lines_get_copied(self, company, journal, accounts):
        origin = _posted_move(company, journal, accounts)
        [debit_note] = AccountDebitNoteWizard.create_debit([origin], copy_lines=True)
        assert debit_note.line_ids.count() == origin.line_ids.count() == 2
        origin_totals = sorted(
            (line.debit, line.credit) for line in origin.line_ids.all())
        debit_note_totals = sorted(
            (line.debit, line.credit) for line in debit_note.line_ids.all())
        assert origin_totals == debit_note_totals

    def test_raises_usererror_when_the_move_is_not_valid(
            self, company, journal, accounts):
        entry = _posted_move(company, journal, accounts, move_type='entry')
        with pytest.raises(UserError):
            AccountDebitNoteWizard.create_debit([entry])
