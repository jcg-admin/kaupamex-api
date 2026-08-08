"""Contrato de ``AccountMoveDebitNote`` — ≙ ``account.move.debit_origin_id``
(``debit_note_ids``/``debit_note_count`` por su reverso).

Portación fiel de ``odoo19c: addons/account_debit_note/models/
account_move.py`` (``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``).
RELATED (DEC-SALE-01, mismo criterio que ``sale_crm.SaleOrderOpportunity``):
``move`` (OneToOne — la nota de débito misma) y ``origin`` (ForeignKey — el
origen, compartible por varias notas).

Requiere ``addons.account_debit_note`` en ``INSTALLED_APPS`` (fuera del
alcance de este porte — ver ``apps.py``) para que la migración cree su tabla.
"""
import pytest
from django.utils import timezone

from addons.account.models import AccountJournal, AccountMove
from addons.account_debit_note.models.account_move import AccountMoveDebitNote
from addons.base.models import ResCompany

pytestmark = pytest.mark.django_db


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(
        name='Ventas', code='VEN', type='sale', company=company)


def _move(company, journal, **kwargs):
    defaults = {
        'move_type': 'out_invoice', 'date': timezone.now().date(),
        'journal': journal, 'company': company,
    }
    defaults.update(kwargs)
    return AccountMove.objects.create(**defaults)


class TestOriginFor:
    def test_without_link_returns_none(self, company, journal):
        move = _move(company, journal)
        assert AccountMoveDebitNote.origin_for(move) is None

    def test_unsaved_move_returns_none(self):
        assert AccountMoveDebitNote.origin_for(AccountMove()) is None

    def test_none_move_returns_none(self):
        assert AccountMoveDebitNote.origin_for(None) is None

    def test_with_link_returns_the_origin(self, company, journal):
        origin = _move(company, journal)
        debit_note = _move(company, journal, move_type='out_invoice')
        AccountMoveDebitNote.objects.create(move=debit_note, origin=origin)
        assert AccountMoveDebitNote.origin_for(debit_note) == origin


class TestDebitNotesFor:
    def test_origin_without_debit_notes_returns_empty(self, company, journal):
        origin = _move(company, journal)
        assert list(AccountMoveDebitNote.debit_notes_for(origin)) == []

    def test_origin_with_several_debit_notes(self, company, journal):
        origin = _move(company, journal)
        debit_note_1 = _move(company, journal)
        debit_note_2 = _move(company, journal)
        AccountMoveDebitNote.objects.create(move=debit_note_1, origin=origin)
        AccountMoveDebitNote.objects.create(move=debit_note_2, origin=origin)
        debit_notes = set(
            AccountMoveDebitNote.debit_notes_for(origin).values_list('pk', flat=True))
        assert debit_notes == {debit_note_1.pk, debit_note_2.pk}


class TestCountFor:
    def test_without_debit_notes_is_zero(self, company, journal):
        origin = _move(company, journal)
        assert AccountMoveDebitNote.count_for(origin) == 0

    def test_counts_the_origins_debit_notes(self, company, journal):
        origin = _move(company, journal)
        debit_note_1 = _move(company, journal)
        debit_note_2 = _move(company, journal)
        AccountMoveDebitNote.objects.create(move=debit_note_1, origin=origin)
        AccountMoveDebitNote.objects.create(move=debit_note_2, origin=origin)
        assert AccountMoveDebitNote.count_for(origin) == 2

    def test_does_not_count_another_origins_debit_notes(self, company, journal):
        origin_a = _move(company, journal)
        origin_b = _move(company, journal)
        debit_note = _move(company, journal)
        AccountMoveDebitNote.objects.create(move=debit_note, origin=origin_b)
        assert AccountMoveDebitNote.count_for(origin_a) == 0


class TestRelatedModel:
    def test_move_is_unique_one_debit_note_one_origin(self, company, journal):
        origin_a = _move(company, journal)
        origin_b = _move(company, journal)
        debit_note = _move(company, journal)
        AccountMoveDebitNote.objects.create(move=debit_note, origin=origin_a)
        with pytest.raises(Exception):
            AccountMoveDebitNote.objects.create(move=debit_note, origin=origin_b)

    def test_origin_admits_several_debit_notes(self, company, journal):
        origin = _move(company, journal)
        debit_note_1 = _move(company, journal)
        debit_note_2 = _move(company, journal)
        AccountMoveDebitNote.objects.create(move=debit_note_1, origin=origin)
        AccountMoveDebitNote.objects.create(move=debit_note_2, origin=origin)
        assert AccountMoveDebitNote.objects.filter(origin=origin).count() == 2

    def test_deleting_the_debit_note_cascades(self, company, journal):
        origin = _move(company, journal)
        debit_note = _move(company, journal)
        AccountMoveDebitNote.objects.create(move=debit_note, origin=origin)
        debit_note.delete()
        assert AccountMoveDebitNote.objects.count() == 0

    def test_str_shows_debit_note_and_origin(self, company, journal):
        origin = _move(company, journal)
        debit_note = _move(company, journal)
        link = AccountMoveDebitNote.objects.create(move=debit_note, origin=origin)
        text = str(link)
        assert '←' in text
