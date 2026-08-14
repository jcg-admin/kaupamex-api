"""Contrato HTTP de ``POST /api/v2/admin/finance/checks/print/`` — UC-FIN-09.

Cierra H-API-406 para ``account_check_printing`` (tarea #50). El caso
exitoso hasta donde el mecanismo llega termina en 500
``CHECK_PRINTING_REPORT_ENGINE_PENDING`` (H-API-407, tarea #280 — el motor
de reportes existe, falta el ``ReportSpec`` del cheque); los tests lo
confirman como el terminal esperado, no como una regresión.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.account.models import AccountJournal, AccountPayment
from addons.account_check_printing.models.account_journal import (
    CheckPrintingJournalSettings,
)
from addons.account_check_printing.models.account_payment import (
    CheckPrintingPaymentInfo,
)
from addons.authz_reauth.models import ReauthSession
from addons.base.models import ResCompany

PRINT_CHECKS_URL = '/api/v2/admin/finance/checks/print/'

pytestmark = pytest.mark.integration


def _elevate(client, user):
    """DEC-12: ``finance.record`` es sensible — sembrar la ventana de
    reautenticación fresca para la sesión ya abierta por ``force_login``."""
    ReauthSession.objects.update_or_create(
        user_id=user.pk, session_key=client.session.session_key or '',
        defaults={'started_at': timezone.now(),
                  'expires_at': timezone.now() + timedelta(seconds=900)})


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='acme-checks', name='ACME Checks')


@pytest.fixture
def journal(company):
    row = AccountJournal.objects.create(
        name='Banco', code='BNK', type='bank', company=company)
    settings = CheckPrintingJournalSettings.ensure_for(row)
    settings.layout = 'account_check_printing.some_report'
    settings.save(update_fields=['layout'])
    return row


def _payment(journal, company, **kwargs):
    defaults = {
        'amount': Decimal('100.00'), 'payment_type': 'outbound',
        'partner_type': 'supplier', 'journal': journal, 'company': company,
        'state': 'draft',
    }
    defaults.update(kwargs)
    return AccountPayment.objects.create(**defaults)


class TestPrintChecksHappyPath:
    def test_numbers_posts_and_marks_sent_then_blocks_on_render(
            self, admin_client, admin_user, journal, company):
        payment = _payment(journal, company)
        _elevate(admin_client, admin_user)

        resp = admin_client.post(
            PRINT_CHECKS_URL,
            {'payment_ids': [payment.pk], 'next_check_number': '00042'},
            format='json',
        )

        assert resp.status_code == 500
        assert resp.data['codigo_error'] == 'CHECK_PRINTING_REPORT_ENGINE_PENDING'
        assert resp.data['payments'] == [
            {'payment_id': payment.pk, 'check_number': '00042',
             'state': 'in_process'},
        ]
        # Side effects reales, ya persistidos — no sólo en la respuesta.
        payment.refresh_from_db()
        assert payment.state == 'in_process'
        row = CheckPrintingPaymentInfo.for_payment(payment)
        assert row.check_number == '00042'
        assert row.is_sent is True


class TestPrintChecksErrors:
    def test_non_numeric_next_check_number_is_400(
            self, admin_client, admin_user, journal, company):
        payment = _payment(journal, company)
        _elevate(admin_client, admin_user)

        resp = admin_client.post(
            PRINT_CHECKS_URL,
            {'payment_ids': [payment.pk], 'next_check_number': 'ABC'},
            format='json',
        )

        assert resp.status_code == 400
        assert resp.data['codigo_error'] == 'CHECK_NUMBER_NOT_NUMERIC'

    def test_missing_check_layout_is_422(
            self, admin_client, admin_user, company):
        journal_sin_layout = AccountJournal.objects.create(
            name='Banco 2', code='BK2', type='bank', company=company)
        payment = _payment(journal_sin_layout, company)
        _elevate(admin_client, admin_user)

        resp = admin_client.post(
            PRINT_CHECKS_URL,
            {'payment_ids': [payment.pk], 'next_check_number': '1'},
            format='json',
        )

        assert resp.status_code == 422
        assert resp.data['codigo_error'] == 'CHECK_LAYOUT_NOT_CONFIGURED'

    def test_duplicate_number_within_journal_is_409(
            self, admin_client, admin_user, journal, company):
        committed = _payment(journal, company, state='in_process')
        CheckPrintingPaymentInfo.objects.create(
            payment=committed, check_number='00043')
        contender = _payment(journal, company, state='draft')
        CheckPrintingPaymentInfo.for_payment(contender, create=True)
        _elevate(admin_client, admin_user)

        resp = admin_client.post(
            PRINT_CHECKS_URL,
            {'payment_ids': [contender.pk], 'next_check_number': '00043'},
            format='json',
        )

        assert resp.status_code == 409
        assert resp.data['codigo_error'] == 'CHECK_NUMBER_DUPLICATE'

    def test_without_capability_is_403(self, auth_client, journal, company):
        payment = _payment(journal, company)

        resp = auth_client.post(
            PRINT_CHECKS_URL,
            {'payment_ids': [payment.pk], 'next_check_number': '1'},
            format='json',
        )

        assert resp.status_code == 403
