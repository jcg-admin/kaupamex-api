"""Contrato de ``CheckPrintingPaymentInfo`` — ≙ los campos ``check_*`` de
``account.payment`` (ver ``models/account_payment.py``).

Requiere ``addons.account_check_printing`` en ``INSTALLED_APPS`` (fuera del
alcance de este porte — ver ``__init__.py`` del paquete) para que la
migración cree sus tablas.
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
from addons.account_check_printing.models.res_currency import (
    apply_account_check_printing_currency_extensions,
)
from addons.base.models import ResCompany, ResCurrency
from exceptions import UserError, ValidationError

apply_account_check_printing_currency_extensions()

pytestmark = pytest.mark.django_db


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(
        name='Banco', code='BNK', type='bank', company=company)


def _payment(journal, company, **kwargs):
    defaults = {
        'amount': Decimal('100.00'), 'payment_type': 'outbound',
        'partner_type': 'supplier', 'journal': journal, 'company': company,
    }
    defaults.update(kwargs)
    return AccountPayment.objects.create(**defaults)


class TestForPayment:
    def test_none_when_not_chosen(self, journal, company):
        payment = _payment(journal, company)
        assert CheckPrintingPaymentInfo.for_payment(payment) is None
        assert CheckPrintingPaymentInfo.is_check_payment(payment) is False

    def test_creates_when_asked(self, journal, company):
        payment = _payment(journal, company)
        row = CheckPrintingPaymentInfo.for_payment(payment, create=True)
        assert row is not None
        assert CheckPrintingPaymentInfo.is_check_payment(payment) is True

    def test_does_not_duplicate_on_repeated_create(self, journal, company):
        payment = _payment(journal, company)
        CheckPrintingPaymentInfo.for_payment(payment, create=True)
        CheckPrintingPaymentInfo.for_payment(payment, create=True)
        assert CheckPrintingPaymentInfo.objects.filter(payment=payment).count() == 1


class TestCleanValidation:
    def test_rejects_non_digit_check_number(self, journal, company):
        payment = _payment(journal, company)
        row = CheckPrintingPaymentInfo.for_payment(payment, create=True)
        row.check_number = 'ABC123'
        with pytest.raises(ValidationError):
            row.save()

    def test_accepts_digits(self, journal, company):
        payment = _payment(journal, company)
        row = CheckPrintingPaymentInfo.for_payment(payment, create=True)
        row.check_number = '00042'
        row.save()
        row.refresh_from_db()
        assert row.check_number == '00042'

    def test_blank_is_valid(self, journal, company):
        payment = _payment(journal, company)
        row = CheckPrintingPaymentInfo.for_payment(payment, create=True)
        row.save()  # no debe alzar con check_number vacío


class TestAmountInWords:
    def test_computes_from_the_payment_currency(self, journal, company):
        # ``ResCompanyManager.create`` ya deja creada (o reusada) la moneda
        # 'MXN' al crear ``company`` — ``get_or_create``, nunca ``create``
        # directo, para no violar el ``unique=True`` de ``ResCurrency.name``.
        currency, _created = ResCurrency.objects.get_or_create(
            name='MXN', defaults={'symbol': '$'})
        payment = _payment(journal, company, currency=currency, amount=Decimal('100.00'))
        row = CheckPrintingPaymentInfo.for_payment(payment, create=True)
        assert row.amount_in_words() == 'CIEN PESOS 00/100 M.N.'

    def test_empty_without_a_currency(self, journal, company):
        payment = _payment(journal, company)
        row = CheckPrintingPaymentInfo.for_payment(payment, create=True)
        assert row.amount_in_words() == ''


class TestComputeCheckNumber:
    def test_empty_without_manual_sequencing(self, journal, company):
        payment = _payment(journal, company)
        row = CheckPrintingPaymentInfo.for_payment(payment, create=True)
        assert row.compute_check_number() == ''

    def test_peeks_with_manual_sequencing(self, journal, company):
        # `ensure_for` y no `objects.create`: con el addon cableado, la señal
        # `post_save` ya creó la fila de ajustes al nacer el diario de banco,
        # así que un `create` choca con el UNIQUE de `journal_id`.
        _settings = CheckPrintingJournalSettings.ensure_for(journal)
        _settings.manual_sequencing = True
        _settings.save(update_fields=['manual_sequencing'])
        payment = _payment(journal, company)
        row = CheckPrintingPaymentInfo.for_payment(payment, create=True)
        assert row.compute_check_number() == '00001'


class TestShowCheckNumber:
    def test_false_without_a_number(self, journal, company):
        payment = _payment(journal, company)
        row = CheckPrintingPaymentInfo.for_payment(payment, create=True)
        assert row.show_check_number() is False

    def test_true_with_a_number(self, journal, company):
        payment = _payment(journal, company)
        row = CheckPrintingPaymentInfo.for_payment(payment, create=True)
        row.check_number = '00001'
        row.save()
        assert row.show_check_number() is True


class TestCheckLayoutAvailable:
    def test_false_with_a_single_layout(self):
        # Sin ningún addon de layout portado en este árbol — ver
        # models/res_company.py.
        assert CheckPrintingPaymentInfo.check_layout_available() is False


class TestUniqueness:
    def test_conflict_between_two_committed_payments(self, journal, company):
        p1 = _payment(journal, company, state='in_process')
        p2 = _payment(journal, company, state='in_process')
        CheckPrintingPaymentInfo.objects.create(payment=p1, check_number='00042')
        CheckPrintingPaymentInfo.objects.create(payment=p2, check_number='00042')
        with pytest.raises(ValidationError):
            CheckPrintingPaymentInfo.validate_check_number_uniqueness(p2)

    def test_no_conflict_when_the_other_is_cancelled(self, journal, company):
        p1 = _payment(journal, company, state='canceled')
        p2 = _payment(journal, company, state='in_process')
        CheckPrintingPaymentInfo.objects.create(payment=p1, check_number='00042')
        CheckPrintingPaymentInfo.objects.create(payment=p2, check_number='00042')
        CheckPrintingPaymentInfo.validate_check_number_uniqueness(p2)  # no debe alzar

    def test_no_conflict_across_different_journals(self, company):
        journal_a = AccountJournal.objects.create(
            name='Banco A', code='BKA', type='bank', company=company)
        journal_b = AccountJournal.objects.create(
            name='Banco B', code='BKB', type='bank', company=company)
        p1 = _payment(journal_a, company, state='in_process')
        p2 = _payment(journal_b, company, state='in_process')
        CheckPrintingPaymentInfo.objects.create(payment=p1, check_number='00042')
        CheckPrintingPaymentInfo.objects.create(payment=p2, check_number='00042')
        CheckPrintingPaymentInfo.validate_check_number_uniqueness(p2)  # no debe alzar


class TestAssignCheckNumberOnPost:
    def test_none_for_a_non_check_payment(self, journal, company):
        payment = _payment(journal, company)
        assert CheckPrintingPaymentInfo.assign_check_number_on_post(payment) is None

    def test_assigns_when_manual_sequencing(self, journal, company):
        # `ensure_for` y no `objects.create`: con el addon cableado, la señal
        # `post_save` ya creó la fila de ajustes al nacer el diario de banco,
        # así que un `create` choca con el UNIQUE de `journal_id`.
        _settings = CheckPrintingJournalSettings.ensure_for(journal)
        _settings.manual_sequencing = True
        _settings.save(update_fields=['manual_sequencing'])
        payment = _payment(journal, company)
        CheckPrintingPaymentInfo.for_payment(payment, create=True)
        row = CheckPrintingPaymentInfo.assign_check_number_on_post(payment)
        assert row.check_number == '00001'

    def test_untouched_without_manual_sequencing(self, journal, company):
        payment = _payment(journal, company)
        CheckPrintingPaymentInfo.for_payment(payment, create=True)
        row = CheckPrintingPaymentInfo.assign_check_number_on_post(payment)
        assert row.check_number == ''


class TestPreparePrintChecks:
    def test_raises_without_eligible_payments(self, journal, company):
        payment = _payment(journal, company)
        with pytest.raises(UserError):
            CheckPrintingPaymentInfo.prepare_print_checks([payment])

    def test_raises_across_different_journals(self, company):
        journal_a = AccountJournal.objects.create(
            name='Banco A', code='BKA', type='bank', company=company)
        journal_b = AccountJournal.objects.create(
            name='Banco B', code='BKB', type='bank', company=company)
        p1 = _payment(journal_a, company)
        p2 = _payment(journal_b, company)
        CheckPrintingPaymentInfo.for_payment(p1, create=True)
        CheckPrintingPaymentInfo.for_payment(p2, create=True)
        with pytest.raises(UserError):
            CheckPrintingPaymentInfo.prepare_print_checks([p1, p2])

    def test_wizard_mode_without_manual_sequencing(self, journal, company):
        payment = _payment(journal, company)
        CheckPrintingPaymentInfo.for_payment(payment, create=True)
        result = CheckPrintingPaymentInfo.prepare_print_checks([payment])
        assert result['mode'] == 'wizard'
        assert result['next_check_number'] == '1'

    def test_print_mode_with_manual_sequencing_needs_a_layout(self, journal, company):
        # `ensure_for` y no `objects.create`: con el addon cableado, la señal
        # `post_save` ya creó la fila de ajustes al nacer el diario de banco,
        # así que un `create` choca con el UNIQUE de `journal_id`.
        _settings = CheckPrintingJournalSettings.ensure_for(journal)
        _settings.manual_sequencing = True
        _settings.save(update_fields=['manual_sequencing'])
        payment = _payment(journal, company)
        CheckPrintingPaymentInfo.for_payment(payment, create=True)
        with pytest.raises(UserError):
            CheckPrintingPaymentInfo.prepare_print_checks([payment])


class TestMarkAsSent:
    def test_requires_a_layout(self, journal, company):
        payment = _payment(journal, company)
        with pytest.raises(UserError):
            CheckPrintingPaymentInfo.mark_as_sent([payment])

    def test_marks_sent_with_a_layout(self, journal, company):
        settings = CheckPrintingJournalSettings.ensure_for(journal)
        settings.layout = 'account_check_printing.some_report'
        settings.save(update_fields=['layout'])
        payment = _payment(journal, company)
        CheckPrintingPaymentInfo.mark_as_sent([payment])
        row = CheckPrintingPaymentInfo.for_payment(payment)
        assert row.is_sent is True


class TestRenderChecks:
    def test_raises_not_implemented(self, journal, company):
        payment = _payment(journal, company)
        with pytest.raises(NotImplementedError):
            CheckPrintingPaymentInfo.render_checks([payment])


class TestVoidCheck:
    def test_sets_state_canceled(self, journal, company):
        payment = _payment(journal, company, state='in_process')
        CheckPrintingPaymentInfo.void_check(payment)
        payment.refresh_from_db()
        assert payment.state == 'canceled'


class TestChecksToPrintQueryset:
    def test_filters_by_journal_state_and_not_sent(self, journal, company):
        p1 = _payment(journal, company, state='in_process')
        p2 = _payment(journal, company, state='draft')
        CheckPrintingPaymentInfo.objects.create(payment=p1, check_number='1')
        CheckPrintingPaymentInfo.objects.create(payment=p2, check_number='2')
        qs = CheckPrintingPaymentInfo.checks_to_print_queryset(journal)
        assert list(qs.values_list('payment_id', flat=True)) == [p1.pk]

    def test_excludes_already_sent(self, journal, company):
        payment = _payment(journal, company, state='in_process')
        row = CheckPrintingPaymentInfo.objects.create(payment=payment, is_sent=True)
        qs = CheckPrintingPaymentInfo.checks_to_print_queryset(journal)
        assert row not in qs
