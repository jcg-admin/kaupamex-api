"""Contrato de ``PrintPrenumberedChecksWizard`` — ≙ el asistente
``print.prenumbered.checks`` (ver ``wizard/print_prenumbered_checks.py``).

``render_checks`` (Divergencia 7 de ``models/account_payment.py``) alza
``NotImplementedError`` como terminal declarado — cada test que llega a ese
punto lo atrapa explícitamente, porque es la parte del flujo genuinamente
bloqueada por la ausencia de un motor de reportes, no un fallo del wizard.
"""
from decimal import Decimal

import pytest

from addons.account.models import AccountJournal, AccountPayment
from addons.account_check_printing.models.account_journal import (
    CheckPrintingJournalSettings,
)
from addons.account_check_printing.models.account_payment import (
    CheckPrintingPaymentInfo,
)
from addons.account_check_printing.wizard.print_prenumbered_checks import (
    PrintPrenumberedChecksWizard,
)
from addons.base.models import ResCompany
from exceptions import ValidationError

pytestmark = pytest.mark.django_db


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.fixture
def journal(company):
    row = AccountJournal.objects.create(
        name='Banco', code='BNK', type='bank', company=company)
    # `ensure_for`: la señal `post_save` ya provisionó la fila al crear el
    # diario de banco; `objects.create` chocaría con el UNIQUE de `journal_id`.
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


class TestValidateNextCheckNumber:
    def test_rejects_non_numeric(self):
        with pytest.raises(ValidationError):
            PrintPrenumberedChecksWizard.validate_next_check_number('ABC')

    def test_accepts_digits(self):
        assert PrintPrenumberedChecksWizard.validate_next_check_number('00042') == '00042'

    def test_accepts_blank(self):
        assert PrintPrenumberedChecksWizard.validate_next_check_number('') == ''


class TestPrintChecks:
    def test_numbers_sequentially_from_the_given_start(self, journal, company):
        payments = [_payment(journal, company) for _ in range(3)]
        for p in payments:
            CheckPrintingPaymentInfo.for_payment(p, create=True)

        with pytest.raises(NotImplementedError):
            PrintPrenumberedChecksWizard.print_checks(payments, '00042')

        numbers = [
            CheckPrintingPaymentInfo.for_payment(p).check_number for p in payments
        ]
        assert numbers == ['00042', '00043', '00044']

    def test_posts_draft_payments(self, journal, company):
        payment = _payment(journal, company, state='draft')
        CheckPrintingPaymentInfo.for_payment(payment, create=True)

        with pytest.raises(NotImplementedError):
            PrintPrenumberedChecksWizard.print_checks([payment], '1')

        payment.refresh_from_db()
        assert payment.state == 'in_process'

    def test_marks_payments_as_sent(self, journal, company):
        payment = _payment(journal, company)
        CheckPrintingPaymentInfo.for_payment(payment, create=True)

        with pytest.raises(NotImplementedError):
            PrintPrenumberedChecksWizard.print_checks([payment], '1')

        row = CheckPrintingPaymentInfo.for_payment(payment)
        assert row.is_sent is True

    def test_rejects_non_numeric_start(self, journal, company):
        payment = _payment(journal, company)
        with pytest.raises(ValidationError):
            PrintPrenumberedChecksWizard.print_checks([payment], 'ABC')

    def test_rejects_duplicate_numbers_within_the_batch(self, journal, company):
        # Dos pagos ya comprometidos (in_process) con números que la
        # numeración secuencial del lote haría colisionar.
        p1 = _payment(journal, company, state='in_process')
        CheckPrintingPaymentInfo.objects.create(
            payment=p1, check_number='00043')

        p2 = _payment(journal, company, state='draft')
        CheckPrintingPaymentInfo.for_payment(p2, create=True)

        with pytest.raises(ValidationError):
            PrintPrenumberedChecksWizard.print_checks([p2], '00043')
