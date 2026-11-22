"""El cron de web-services de ``account_edi``.

≙ ``ir_cron_edi_network`` (``odoo19c: addons/account_edi/data/cron.xml:2-10``),
su activación al crear un formato con web-service (``account_edi_format.py:
40-42``) y su disparo cuando quedan trabajos (``account_edi_document.py:
250-251``). Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/
designs/account-edi-network-cron.md``.

*Métrica:* el ``active`` del cron y sus disparos registrados.
*Ciega a:* el envío real a un web-service, que es de cada localización.
"""
import datetime

import pytest

from addons.account.models import AccountJournal, AccountMove
from addons.account_edi.data import CRON_EDI_NETWORK
from addons.account_edi.models.account_move import (
    _create_edi_documents_after_post, button_cancel)
from addons.account_edi.models.account_edi_document import AccountEdiDocument
from addons.account_edi.models.account_edi_format import AccountEdiFormat
from addons.base.data.cron import sembrar_cron_vivo
from addons.base.models import ResCompany
from addons.base.models.ir_cron import IrCronTrigger
from orm.environments import context_scope, env, sudo

pytestmark = pytest.mark.django_db


@pytest.fixture
def cron():
    sembrar_cron_vivo(CRON_EDI_NETWORK)
    return env().ref('account_edi.ir_cron_edi_network')


def test_the_cron_is_seeded_inactive_with_its_external_id(cron):
    assert cron.active is False
    assert cron.method_name == '_cron_process_documents_web_services'


def test_a_format_with_web_services_activates_it(cron, monkeypatch):
    monkeypatch.setattr(AccountEdiFormat, '_needs_web_services',
                        lambda self: True)
    with sudo():
        env()['account.edi.format'].create({'name': 'WS', 'code': 'edi_ws_c'})
    cron.refresh_from_db()
    assert cron.active is True


def test_a_format_without_web_services_leaves_it_inactive(cron):
    with sudo():
        env()['account.edi.format'].create({'name': 'Plano',
                                            'code': 'edi_plain_c'})
    cron.refresh_from_db()
    assert cron.active is False


def test_remaining_jobs_trigger_the_cron_again(cron, monkeypatch):
    # Un cron inactivo descarta los disparos ya vencidos, como en la fuente
    # (``odoo19c: odoo/addons/base/models/ir_cron.py:764-792``).
    cron.write({'active': True})
    monkeypatch.setattr(AccountEdiDocument, '_process_documents_web_services',
                        classmethod(lambda cls, docs, job_count=None: 3))
    before = IrCronTrigger.objects.filter(cron_id=cron.pk).count()
    AccountEdiDocument._cron_process_documents_web_services()
    assert IrCronTrigger.objects.filter(cron_id=cron.pk).count() == before + 1


@pytest.fixture
def move(db):
    company = ResCompany.objects.create(code='edi_cron', name='EDI cron')
    journal = AccountJournal.objects.create(
        name='Ventas', code='VEN', type='sale', company=company)
    return AccountMove.objects.create(
        company=company, journal=journal, date=datetime.date.today())


def _triggers(cron):
    return IrCronTrigger.objects.filter(cron_id=cron.pk).count()


def test_posting_a_move_triggers_the_cron(cron, move):
    # ``AccountMove`` es modelo de Django: el disparo no puede leer
    # ``self.env``, lo lee del entorno de la petición.
    cron.write({'active': True})
    before = _triggers(cron)
    _create_edi_documents_after_post(move)
    assert _triggers(cron) == before + 1


def test_the_skip_context_does_not_trigger_on_post(cron, move):
    cron.write({'active': True})
    before = _triggers(cron)
    with context_scope(skip_account_edi_cron_trigger=True):
        _create_edi_documents_after_post(move)
    assert _triggers(cron) == before


def test_cancelling_a_move_triggers_the_cron(cron, move):
    cron.write({'active': True})
    before = _triggers(cron)
    button_cancel(move)
    assert _triggers(cron) == before + 1


def test_the_cron_passes_job_count_to_its_method(cron, monkeypatch):
    received = {}

    def probe(cls, job_count=None):
        received['job_count'] = job_count
    monkeypatch.setattr(AccountEdiDocument,
                        '_cron_process_documents_web_services',
                        classmethod(probe))
    cron._callback()
    assert received == {'job_count': 20}
