"""Contrato HTTP de ``POST /api/v2/admin/finance/invoices/{id}/register-payment/``
— UC-PAY-14 (:ref:`uc-pay-14-pago-parcial-abono`).

Cierra H-API-408 para la parte de acción (tarea #55): el álgebra de
conciliación (``AccountPartialReconcile``/``AccountFullReconcile``) ya
estaba portada y probada — estos tests ejercen los tres criterios de
aceptación del UC (AC-01/AC-02/AC-03) end-to-end vía HTTP, más las
condiciones de error de PARTE 5.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.account.models import (
    AccountAccount, AccountJournal, AccountMove, AccountMoveLine,
    AccountPartialReconcile,
)
from addons.authz_reauth.models import ReauthSession
from addons.base.models import ResCompany

pytestmark = pytest.mark.integration


def _register_payment_url(pk):
    return f'/api/v2/admin/finance/invoices/{pk}/register-payment/'


def _elevate(client, user):
    """DEC-12: ``finance.record`` es sensible — sembrar la ventana de
    reautenticación fresca para la sesión ya abierta por ``force_login``."""
    ReauthSession.objects.update_or_create(
        user_id=user.pk, session_key=client.session.session_key or '',
        defaults={'started_at': timezone.now(),
                  'expires_at': timezone.now() + timedelta(seconds=900)})


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='acme-pay', name='ACME Pay')


@pytest.fixture
def sale_journal(company):
    return AccountJournal.objects.create(
        name='Ventas', code='VEN', type='sale', company=company)


@pytest.fixture
def accounts(company):
    receivable = AccountAccount.objects.create(
        code='105', name='Clientes', account_type='asset_receivable',
        company=company)
    income = AccountAccount.objects.create(
        code='401', name='Ventas', account_type='income', company=company)
    bank = AccountAccount.objects.create(
        code='102', name='Bancos', account_type='asset_cash', company=company)
    writeoff = AccountAccount.objects.create(
        code='701', name='Diferencias de pago', account_type='expense_other',
        company=company)
    return receivable, income, bank, writeoff


@pytest.fixture
def bank_journal(company, accounts):
    _, _, bank, _ = accounts
    return AccountJournal.objects.create(
        name='Banco', code='BNK', type='bank', company=company,
        default_account=bank)


def _posted_invoice(company, sale_journal, accounts, amount=Decimal('1000.00')):
    receivable, income, _bank, _writeoff = accounts
    move = AccountMove.objects.create(
        move_type='out_invoice', date=timezone.now().date(),
        journal=sale_journal, company=company, state='posted')
    AccountMoveLine.objects.create(move=move, account=receivable, debit=amount)
    AccountMoveLine.objects.create(move=move, account=income, credit=amount)
    return move


class TestRegisterPaymentHappyPath:
    def test_ac01_partial_payment_leaves_open_balance(
            self, admin_client, admin_user, company, sale_journal,
            bank_journal, accounts):
        """AC-01: abono de $600 sobre saldo $1000 deja $400 abiertos."""
        move = _posted_invoice(company, sale_journal, accounts)
        _elevate(admin_client, admin_user)

        resp = admin_client.post(
            _register_payment_url(move.pk),
            {'amount': '600.00', 'journal_id': bank_journal.pk},
            format='json')

        assert resp.status_code == 201
        assert resp.data['payment_state'] == 'partial'
        assert Decimal(resp.data['amount_residual']) == Decimal('400.00')
        assert len(resp.data['partial_reconcile_ids']) == 1

        move.refresh_from_db()
        assert move.payment_state == 'partial'
        assert move.get_amount_residual() == Decimal('400.00')

    def test_ac02_second_payment_closes_via_full_reconcile(
            self, admin_client, admin_user, company, sale_journal,
            bank_journal, accounts):
        """AC-02: segundo abono de $400 llega a $0 y agrupa ambos partials
        bajo el mismo ``account.full.reconcile``."""
        move = _posted_invoice(company, sale_journal, accounts)
        _elevate(admin_client, admin_user)

        first = admin_client.post(
            _register_payment_url(move.pk),
            {'amount': '600.00', 'journal_id': bank_journal.pk},
            format='json')
        assert first.status_code == 201

        second = admin_client.post(
            _register_payment_url(move.pk),
            {'amount': '400.00', 'journal_id': bank_journal.pk},
            format='json')

        assert second.status_code == 201
        assert second.data['payment_state'] == 'paid'
        assert Decimal(second.data['amount_residual']) == Decimal('0.00')

        move.refresh_from_db()
        assert move.payment_state == 'paid'
        receivable_line = move.line_ids.get(account__account_type='asset_receivable')
        partials = AccountPartialReconcile.objects.filter(debit_move=receivable_line)
        assert partials.count() == 2
        full_ids = {p.full_reconcile_id for p in partials}
        assert full_ids == {partials.first().full_reconcile_id}
        assert None not in full_ids

    def test_ac03_writeoff_closes_in_one_step(
            self, admin_client, admin_user, company, sale_journal,
            bank_journal, accounts):
        """AC-03: abono de $600 con ``difference_handling='reconcile'``
        crea un apunte de $400 en la cuenta de diferencia y concilia todo
        en el mismo paso."""
        move = _posted_invoice(company, sale_journal, accounts)
        _, _, _bank, writeoff_account = accounts
        _elevate(admin_client, admin_user)

        resp = admin_client.post(
            _register_payment_url(move.pk),
            {'amount': '600.00', 'journal_id': bank_journal.pk,
             'difference_handling': 'reconcile',
             'difference_account_id': writeoff_account.pk},
            format='json')

        assert resp.status_code == 201
        assert resp.data['payment_state'] == 'paid'
        assert Decimal(resp.data['amount_residual']) == Decimal('0.00')
        assert len(resp.data['partial_reconcile_ids']) == 2

        payment_move = AccountMove.objects.get(pk=resp.data['payment_move_id'])
        writeoff_line = payment_move.line_ids.get(account=writeoff_account)
        assert writeoff_line.debit == Decimal('400.00')


class TestRegisterPaymentErrors:
    def test_amount_exceeding_residual_is_409(
            self, admin_client, admin_user, company, sale_journal,
            bank_journal, accounts):
        move = _posted_invoice(company, sale_journal, accounts)
        _elevate(admin_client, admin_user)

        resp = admin_client.post(
            _register_payment_url(move.pk),
            {'amount': '1500.00', 'journal_id': bank_journal.pk},
            format='json')

        assert resp.status_code == 409
        assert resp.data['codigo_error'] == 'AMOUNT_EXCEEDS_RESIDUAL'

    def test_writeoff_without_account_is_400(
            self, admin_client, admin_user, company, sale_journal,
            bank_journal, accounts):
        move = _posted_invoice(company, sale_journal, accounts)
        _elevate(admin_client, admin_user)

        resp = admin_client.post(
            _register_payment_url(move.pk),
            {'amount': '600.00', 'journal_id': bank_journal.pk,
             'difference_handling': 'reconcile'},
            format='json')

        assert resp.status_code == 400
        # ``validate()`` a nivel objeto envuelve el dict en una lista de
        # ErrorDetail (mismo patrón que ORDER_REQUIRED en
        # ``delivery/test_logistics_endpoints.py``) — no queda plano.
        assert resp.data['codigo_error'][0] == 'DIFFERENCE_ACCOUNT_REQUIRED'

    def test_unposted_invoice_is_422(
            self, admin_client, admin_user, company, sale_journal,
            bank_journal, accounts):
        receivable, income, _bank, _writeoff = accounts
        draft = AccountMove.objects.create(
            move_type='out_invoice', date=timezone.now().date(),
            journal=sale_journal, company=company)
        _elevate(admin_client, admin_user)

        resp = admin_client.post(
            _register_payment_url(draft.pk),
            {'amount': '100.00', 'journal_id': bank_journal.pk},
            format='json')

        assert resp.status_code == 422
        assert resp.data['codigo_error'] == 'INVOICE_NOT_POSTED'

    def test_invoice_not_found_is_404(
            self, admin_client, admin_user, bank_journal):
        _elevate(admin_client, admin_user)

        resp = admin_client.post(
            _register_payment_url(999999),
            {'amount': '100.00', 'journal_id': bank_journal.pk},
            format='json')

        assert resp.status_code == 404
        assert resp.data['codigo_error'] == 'INVOICE_NOT_FOUND'

    def test_without_capability_is_403(
            self, auth_client, company, sale_journal, bank_journal, accounts):
        move = _posted_invoice(company, sale_journal, accounts)

        resp = auth_client.post(
            _register_payment_url(move.pk),
            {'amount': '100.00', 'journal_id': bank_journal.pk},
            format='json')

        assert resp.status_code == 403
