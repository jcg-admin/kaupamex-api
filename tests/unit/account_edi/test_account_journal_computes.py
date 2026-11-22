"""Los dos cómputos que ``account_edi`` declara sobre ``account.journal``.

≙ ``edi_format_ids`` y ``compatible_edi_ids`` (``odoo19c: addons/account_edi/
models/account_journal.py:11-20``), sus cómputos (``:46-79``) y el ``create``
del formato que recalcula los diarios (``account_edi_format.py:24-44``).
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
account-edi-journal-computes.md``.

*Métrica:* los formatos de cada diario tras cambiar su tipo, crear un formato
o proteger uno con un documento pendiente.
*Ciega a:* los formatos concretos de las localizaciones; aquí la
compatibilidad y el defecto se sustituyen por código.
"""
import pytest
from django.utils import timezone

from addons.account.models import AccountJournal, AccountMove
from addons.account_edi.models.account_edi_document import AccountEdiDocument
from addons.account_edi.models.account_edi_format import AccountEdiFormat
from addons.base.models import ResCompany
from orm.environments import env, sudo

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(AccountEdiFormat, '_is_compatible_with_journal',
                        lambda self, journal: journal.type == 'sale')
    monkeypatch.setattr(AccountEdiFormat, '_is_enabled_by_default_on_journal',
                        lambda self, journal: True)
    with sudo():
        company = ResCompany.objects.create(code='edi-k', name='EDI K')
        edi_format = AccountEdiFormat.objects.create(name='Formato',
                                                     code='edi_k')
    return company, edi_format


def _journal(company, code, journal_type):
    with sudo():
        return env()['account.journal'].create({
            'name': code, 'code': code, 'type': journal_type,
            'company': company.pk})


def test_the_type_drives_the_formats(setup):
    company, edi_format = setup
    journal = _journal(company, 'KS1', 'sale')
    with sudo():
        assert journal.edi_format_ids.ids == [edi_format.pk]
        journal.write({'type': 'general'})
        assert not journal.edi_format_ids


def test_compatible_formats_are_a_recordset(setup):
    company, edi_format = setup
    journal = _journal(company, 'KS2', 'sale')
    with sudo():
        assert journal.compatible_edi_ids._name == 'account.edi.format'
        assert journal.compatible_edi_ids.ids == [edi_format.pk]


def test_creating_a_format_enables_it_on_the_journals(setup):
    company, edi_format = setup
    journal = _journal(company, 'KS3', 'sale')
    with sudo():
        new_format = env()['account.edi.format'].create(
            {'name': 'Nuevo', 'code': 'edi_k_new'})
        journal.invalidate_recordset()
        assert set(journal.edi_format_ids.ids) == {
            edi_format.pk, new_format.id}


def test_each_journal_keeps_its_own_protected_formats(setup, monkeypatch):
    company, edi_format = setup
    first = _journal(company, 'KS4', 'sale')
    second = _journal(company, 'KS5', 'sale')
    with sudo():
        # El cómputo del alta es perezoso: se lee antes de cambiar el defecto.
        assert (first | second).mapped('edi_format_ids').ids == [edi_format.pk]
    with sudo():
        move = AccountMove.objects.create(
            move_type='entry', date=timezone.now().date(),
            journal=AccountJournal.objects.get(pk=first.id), company=company)
    AccountEdiDocument.objects.create(move_id=move, edi_format_id=edi_format,
                                      state='to_send')
    monkeypatch.setattr(AccountEdiFormat, '_is_enabled_by_default_on_journal',
                        lambda self, journal: False)
    with sudo():
        (first | second).write({'type': 'general'})
        assert first.edi_format_ids.ids == [edi_format.pk]
        assert not second.edi_format_ids
