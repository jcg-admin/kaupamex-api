"""Contrato de ``JournalDebitSequence`` — ≙ ``account.journal.debit_sequence``.

Portación fiel del campo del addon ``account_debit_note`` de Odoo 19
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, ``odoo19c:
addons/account_debit_note/models/account_journal.py``). RELATED OneToOne
(DEC-SALE-01, mismo criterio que ``account_add_gln``): cada test verifica un
comportamiento del original o del vínculo que lo porta.

Requiere ``addons.account_debit_note`` en ``INSTALLED_APPS`` (fuera del
alcance de este porte — ver ``apps.py``) para que la migración cree su tabla.
"""
import pytest
from django.utils import timezone

from addons.account.models import AccountJournal
from addons.account_debit_note.models.account_journal import JournalDebitSequence
from addons.base.models import ResCompany

pytestmark = pytest.mark.django_db


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='acme', name='ACME')


def _journal(company, **kwargs):
    defaults = {'name': 'Diario', 'code': 'DIA', 'type': 'sale', 'company': company}
    defaults.update(kwargs)
    return AccountJournal.objects.create(**defaults)


class TestDefaultForType:
    def test_sale_defaults_true(self):
        # ≙ _compute_debit_sequence: journal.type in ("sale", "purchase")
        assert JournalDebitSequence.default_for_type('sale') is True

    def test_purchase_defaults_true(self):
        assert JournalDebitSequence.default_for_type('purchase') is True

    def test_bank_defaults_false(self):
        assert JournalDebitSequence.default_for_type('bank') is False

    def test_general_defaults_false(self):
        assert JournalDebitSequence.default_for_type('general') is False


class TestWantsDebitSequence:
    def test_none_journal_is_false(self):
        assert JournalDebitSequence.wants_debit_sequence(None) is False

    def test_without_override_row_uses_default_for_type(self, company):
        # Diario creado antes de instalar el addon, o nunca sincronizado —
        # el valor efectivo es el default por tipo (≙ el primer recompute
        # de Odoo).
        journal = _journal(company, type='purchase')
        assert JournalDebitSequence.wants_debit_sequence(journal) is True

    def test_with_override_row_saved_value_wins(self, company):
        journal = _journal(company, type='sale')
        JournalDebitSequence.objects.create(journal=journal, debit_sequence=False)
        assert JournalDebitSequence.wants_debit_sequence(journal) is False

    def test_bank_journal_without_override_is_false(self, company):
        journal = _journal(company, type='bank', code='BNK')
        assert JournalDebitSequence.wants_debit_sequence(journal) is False


class TestSyncFromType:
    def test_creates_the_row_when_missing(self, company):
        journal = _journal(company, type='sale')
        row = JournalDebitSequence.sync_from_type(journal)
        assert row.debit_sequence is True
        assert JournalDebitSequence.objects.filter(journal=journal).count() == 1

    def test_recalculates_when_already_exists(self, company):
        journal = _journal(company, type='sale')
        JournalDebitSequence.objects.create(journal=journal, debit_sequence=False)
        row = JournalDebitSequence.sync_from_type(journal)
        row.refresh_from_db()
        assert row.debit_sequence is True


class TestRelatedModel:
    def test_one_to_one_reverse_on_journal(self, company):
        journal = _journal(company)
        row = JournalDebitSequence.objects.create(journal=journal, debit_sequence=True)
        assert journal.debit_sequence_setting == row

    def test_one_to_one_is_unique(self, company):
        journal = _journal(company)
        JournalDebitSequence.objects.create(journal=journal)
        with pytest.raises(Exception):
            JournalDebitSequence.objects.create(journal=journal)

    def test_delete_cascades_from_the_journal(self, company):
        journal = _journal(company)
        JournalDebitSequence.objects.create(journal=journal, debit_sequence=True)
        journal.delete()
        assert JournalDebitSequence.objects.count() == 0

    def test_str_includes_the_journal(self, company):
        journal = _journal(company, code='VEN')
        row = JournalDebitSequence.objects.create(journal=journal, debit_sequence=True)
        assert 'VEN' in str(row) or journal.code in str(row.journal)

    def test_timestamped(self, company):
        journal = _journal(company)
        before = timezone.now()
        row = JournalDebitSequence.objects.create(journal=journal)
        assert row.created_at >= before
        assert row.updated_at >= before
