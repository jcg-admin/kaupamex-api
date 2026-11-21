"""``write`` de ``account.journal`` extendido por ``account_edi``.

≙ ``odoo19c: addons/account_edi/models/account_journal.py:25-41``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
account-edi-journal-write.md``.

*Métrica:* el estado de ``edi_format_ids`` y de los documentos tras la
escritura.
*Ciega a:* los formatos concretos con web-service, que la referencia declara
en otros addons; aquí se sustituye ``_needs_web_services`` por código.
"""
import pytest
from django.db import transaction
from django.utils import timezone

import fields
from addons.account.models import AccountJournal, AccountMove
from addons.account_edi.models.account_edi_document import AccountEdiDocument
from addons.account_edi.models.account_edi_format import AccountEdiFormat
from addons.base.models import ResCompany
from exceptions import UserError
from orm.environments import sudo

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(AccountEdiFormat, '_needs_web_services',
                        lambda self: self.code == 'edi_ws')
    with sudo():
        company = ResCompany.objects.create(code='edi-w', name='EDI W')
        journal = AccountJournal.objects.create(
            name='Ventas', code='SEDW', type='sale', company=company)
        ws = AccountEdiFormat.objects.create(name='Con servicio',
                                             code='edi_ws')
        plain = AccountEdiFormat.objects.create(name='Sin servicio',
                                                code='edi_plain')
        journal.write({'edi_format_ids': [fields.Command.set([ws.pk,
                                                              plain.pk])]})
        move = AccountMove.objects.create(
            move_type='entry', date=timezone.now().date(),
            journal=journal, company=company)
    return journal, ws, plain, move


def _document(move, edi_format, state):
    return AccountEdiDocument.objects.create(
        move_id=move, edi_format_id=edi_format, state=state)


def test_removing_a_web_service_format_with_pending_documents_fails(setup):
    journal, ws, plain, move = setup
    _document(move, ws, 'to_send')
    with sudo():
        with pytest.raises(UserError):
            with transaction.atomic():
                journal.write({'edi_format_ids': [fields.Command.set(
                    [plain.pk])]})
        journal.invalidate_recordset()
        assert set(journal.edi_format_ids.ids) == {ws.pk, plain.pk}


def test_removing_a_plain_format_deletes_its_pending_documents(setup):
    journal, ws, plain, move = setup
    pending = _document(move, plain, 'to_send')
    cancelling = _document(move, plain, 'to_cancel')
    with sudo():
        journal.write({'edi_format_ids': [fields.Command.set([ws.pk])]})
        assert set(journal.edi_format_ids.ids) == {ws.pk}
    assert not AccountEdiDocument.objects.filter(
        pk__in=[pending.pk, cancelling.pk]).exists()


def test_a_sent_document_of_a_removed_format_survives(setup):
    journal, ws, plain, move = setup
    sent = _document(move, plain, 'sent')
    with sudo():
        journal.write({'edi_format_ids': [fields.Command.set([ws.pk])]})
    assert AccountEdiDocument.objects.filter(pk=sent.pk).exists()


def test_a_write_that_keeps_the_formats_leaves_documents_alone(setup):
    journal, ws, plain, move = setup
    pending = _document(move, plain, 'to_send')
    with sudo():
        journal.write({'name': 'Ventas MX'})
    assert AccountEdiDocument.objects.filter(pk=pending.pk).exists()
