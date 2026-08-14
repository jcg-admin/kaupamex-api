"""Contrato HTTP de ``POST /api/v2/admin/finance/debit-notes/`` — UC-FIN-10.

Cierra H-API-406 para ``account_debit_note`` (tarea #51).
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.account.models import (
    AccountAccount, AccountJournal, AccountMove, AccountMoveLine,
)
from addons.account_debit_note.models.account_move import AccountMoveDebitNote
from addons.authz_reauth.models import ReauthSession
from addons.base.models import ResCompany

CREATE_DEBIT_NOTE_URL = '/api/v2/admin/finance/debit-notes/'

pytestmark = pytest.mark.integration


def _elevate(client, user):
    """DEC-12: ``invoices`` es sensible — sembrar la ventana de
    reautenticación fresca para la sesión ya abierta por ``force_login``."""
    ReauthSession.objects.update_or_create(
        user_id=user.pk, session_key=client.session.session_key or '',
        defaults={'started_at': timezone.now(),
                  'expires_at': timezone.now() + timedelta(seconds=900)})


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='acme-debit', name='ACME Debit')


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(
        name='Ventas', code='VEN', type='sale', company=company)


@pytest.fixture
def accounts(company):
    receivable = AccountAccount.objects.create(
        code='105', name='Clientes', account_type='asset_receivable',
        company=company)
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


class TestCreateDebitNoteHappyPath:
    def test_creates_a_draft_debit_note_linked_to_origin(
            self, admin_client, admin_user, company, journal, accounts):
        move = _posted_move(company, journal, accounts)
        _elevate(admin_client, admin_user)

        resp = admin_client.post(
            CREATE_DEBIT_NOTE_URL, {'move_ids': [move.pk], 'reason': 'ajuste'},
            format='json',
        )

        assert resp.status_code == 201
        assert len(resp.data) == 1
        created = resp.data[0]
        assert created['state'] == 'draft'
        assert created['move_type'] == 'out_invoice'
        assert created['ref'] == f'{move.name}, ajuste'
        new_move = AccountMove.objects.get(pk=created['id'])
        assert AccountMoveDebitNote.origin_for(new_move) == move


class TestCreateDebitNoteErrors:
    def test_unposted_move_is_422(
            self, admin_client, admin_user, company, journal, accounts):
        receivable, income = accounts
        move = AccountMove.objects.create(
            move_type='out_invoice', date=timezone.now().date(),
            journal=journal, company=company, state='draft')
        _elevate(admin_client, admin_user)

        resp = admin_client.post(
            CREATE_DEBIT_NOTE_URL, {'move_ids': [move.pk]}, format='json')

        assert resp.status_code == 422
        assert resp.data['codigo_error'] == 'DEBIT_NOTE_MOVE_NOT_POSTED'

    def test_already_linked_move_is_409(
            self, admin_client, admin_user, company, journal, accounts):
        # ``origin_for(move)`` es no-None cuando ``move`` YA ES una nota de
        # débito (tiene su propio origen) — la condición de la referencia
        # impide debitar una nota de débito, no "un movimiento ya debitado".
        grandparent = _posted_move(company, journal, accounts)
        already_a_debit_note = _posted_move(company, journal, accounts)
        AccountMoveDebitNote.objects.create(
            move=already_a_debit_note, origin=grandparent)
        _elevate(admin_client, admin_user)

        resp = admin_client.post(
            CREATE_DEBIT_NOTE_URL, {'move_ids': [already_a_debit_note.pk]},
            format='json')

        assert resp.status_code == 409
        assert resp.data['codigo_error'] == 'DEBIT_NOTE_ALREADY_LINKED'

    def test_invalid_move_type_is_422(
            self, admin_client, admin_user, company, journal, accounts):
        move = _posted_move(company, journal, accounts, move_type='entry')
        _elevate(admin_client, admin_user)

        resp = admin_client.post(
            CREATE_DEBIT_NOTE_URL, {'move_ids': [move.pk]}, format='json')

        assert resp.status_code == 422
        assert resp.data['codigo_error'] == 'DEBIT_NOTE_INVALID_MOVE_TYPE'

    def test_without_capability_is_403(
            self, auth_client, company, journal, accounts):
        move = _posted_move(company, journal, accounts)

        resp = auth_client.post(
            CREATE_DEBIT_NOTE_URL, {'move_ids': [move.pk]}, format='json')

        assert resp.status_code == 403
