"""Contrato de ``CheckPrintingJournalSettings`` — ≙ los campos ``check_*``/
``bank_check_printing_layout`` de ``account.journal`` (ver
``models/account_journal.py``).

Requiere ``addons.account_check_printing`` en ``INSTALLED_APPS`` (fuera del
alcance de este porte — ver ``__init__.py`` del paquete) para que la
migración cree sus tablas.
"""
import pytest

from addons.account.models import AccountJournal
from addons.account_check_printing.models.account_journal import (
    MAX_INT32,
    CheckPrintingJournalSettings,
    on_journal_saved,
)
from addons.base.models import ResCompany
from exceptions import ValidationError

pytestmark = pytest.mark.django_db


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='acme', name='ACME')


def _journal(company, **kwargs):
    defaults = {'name': 'Banco', 'code': 'BNK', 'type': 'bank', 'company': company}
    defaults.update(kwargs)
    return AccountJournal.objects.create(**defaults)


class TestEnsureCheckSequence:
    def test_creates_a_sequence_when_missing(self, company):
        journal = _journal(company)
        row = CheckPrintingJournalSettings.ensure_check_sequence(journal)
        assert row.sequence_id is not None
        assert row.sequence.padding == 5
        assert row.sequence.implementation == 'no_gap'
        assert row.sequence.company_id == company.pk

    def test_is_idempotent(self, company):
        journal = _journal(company)
        first = CheckPrintingJournalSettings.ensure_check_sequence(journal)
        second = CheckPrintingJournalSettings.ensure_check_sequence(journal)
        assert first.sequence_id == second.sequence_id


class TestSyncBankJournal:
    def test_bank_journal_gets_a_sequence(self, company):
        journal = _journal(company, type='bank')
        row = CheckPrintingJournalSettings.sync_bank_journal(journal)
        assert row is not None
        assert row.sequence_id is not None

    def test_non_bank_journal_is_skipped(self, company):
        journal = _journal(company, type='sale', code='VEN')
        row = CheckPrintingJournalSettings.sync_bank_journal(journal)
        assert row is None
        assert not CheckPrintingJournalSettings.objects.filter(journal=journal).exists()


class TestOnJournalSavedSignal:
    def test_new_bank_journal_is_provisioned(self, company):
        journal = AccountJournal(name='Banco', code='BN2', type='bank', company=company)
        journal.save()
        on_journal_saved(sender=AccountJournal, instance=journal, created=True)
        assert CheckPrintingJournalSettings.objects.filter(journal=journal).exists()

    def test_update_does_not_reprovision(self, company):
        journal = _journal(company)
        CheckPrintingJournalSettings.ensure_check_sequence(journal)
        row_before = CheckPrintingJournalSettings.objects.get(journal=journal)
        on_journal_saved(sender=AccountJournal, instance=journal, created=False)
        row_after = CheckPrintingJournalSettings.objects.get(journal=journal)
        assert row_before.pk == row_after.pk

    def test_non_bank_journal_is_not_provisioned(self, company):
        journal = AccountJournal(name='Ventas', code='VEN', type='sale', company=company)
        journal.save()
        on_journal_saved(sender=AccountJournal, instance=journal, created=True)
        assert not CheckPrintingJournalSettings.objects.filter(journal=journal).exists()


class TestNextCheckNumber:
    def test_without_sequence_defaults_to_one(self, company):
        # Diario NO de banco a propósito: con el addon cableado, la señal
        # `post_save` provisiona la secuencia de todo diario de banco nuevo
        # (`sync_bank_journal`), así que "fila de ajustes SIN secuencia" ya no
        # es un estado alcanzable para `type='bank'` — daría '00001'. En un
        # diario que no es de banco la señal no provisiona nada, que es donde
        # el default '1' de la referencia sigue siendo observable.
        journal = _journal(company, type='sale', code='VEN1')
        row = CheckPrintingJournalSettings.ensure_for(journal)
        assert row.sequence_id is None
        assert row.next_check_number() == '1'

    def test_peeks_without_consuming(self, company):
        journal = _journal(company)
        row = CheckPrintingJournalSettings.ensure_check_sequence(journal)
        first = row.next_check_number()
        second = row.next_check_number()
        assert first == second == '00001'


class TestSetNextCheckNumber:
    def test_rejects_non_numeric(self, company):
        journal = _journal(company)
        row = CheckPrintingJournalSettings.ensure_for(journal)
        with pytest.raises(ValidationError):
            row.set_next_check_number('F1234')

    def test_rejects_going_backwards(self, company):
        journal = _journal(company)
        row = CheckPrintingJournalSettings.ensure_check_sequence(journal)
        row.sequence.number_next = 100
        row.sequence.save(update_fields=['number_next'])
        with pytest.raises(ValidationError):
            row.set_next_check_number('50')

    def test_rejects_over_max_int32(self, company):
        journal = _journal(company)
        row = CheckPrintingJournalSettings.ensure_for(journal)
        with pytest.raises(ValidationError):
            row.set_next_check_number(str(MAX_INT32 + 1))

    def test_accepts_max_int32(self, company):
        journal = _journal(company)
        row = CheckPrintingJournalSettings.ensure_for(journal)
        row.set_next_check_number(str(MAX_INT32))
        row.refresh_from_db()
        assert row.sequence.number_next == MAX_INT32

    def test_updates_padding_to_the_written_width(self, company):
        journal = _journal(company)
        row = CheckPrintingJournalSettings.ensure_for(journal)
        row.set_next_check_number('00042')
        row.refresh_from_db()
        assert row.sequence.padding == 5
        assert row.sequence.number_next == 42

    def test_creates_the_sequence_lazily_when_missing(self, company):
        # Diario NO de banco por la misma razón que
        # `test_without_sequence_defaults_to_one`: es el único caso en que la
        # fila nace sin secuencia, que es la precondición de la creación
        # perezosa que este test ejerce.
        journal = _journal(company, type='sale', code='VEN2')
        row = CheckPrintingJournalSettings.ensure_for(journal)
        assert row.sequence_id is None
        row.set_next_check_number('7')
        row.refresh_from_db()
        assert row.sequence_id is not None
        assert row.sequence.number_next == 7


class TestEffectiveLayout:
    def test_journal_layout_wins(self, company):
        journal = _journal(company)
        row = CheckPrintingJournalSettings.ensure_for(journal)
        row.layout = 'account_check_printing.custom_report'
        row.save(update_fields=['layout'])
        assert row.effective_layout() == 'account_check_printing.custom_report'

    def test_falls_back_to_the_company_default(self, company):
        journal = _journal(company)
        row = CheckPrintingJournalSettings.ensure_for(journal)
        assert row.effective_layout() == 'disabled'
