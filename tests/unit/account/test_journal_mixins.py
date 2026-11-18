"""``account.journal`` hereda de verdad tres de sus cuatro mixins.

≙ ``_inherit`` (``odoo19c: addons/account/models/account_journal.py:46``):
``portal.mixin``, ``mail.alias.mixin.optional``, ``mail.thread`` y
``mail.activity.mixin``. El segundo no existe aquí (TASK-GEN-0413).
Diseño en ``designs/account-journal-mixins.md`` del Workbench.

Métrica: el MRO de la clase y las filas de ``mail_message``,
``mail_activity`` y ``account_journal`` leídas tras cada llamada.
Ciega a: el seguimiento de campos y el alias de correo.
"""
import pytest

from addons.account.models import AccountJournal
from addons.base.models import ResCompany
from addons.mail.models import (
    MailActivity, MailActivityMixin, MailMessage, MailThread)
from addons.portal.models.portal_mixin import PortalMixin
from orm.environments import sudo
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def journal():
    company = ResCompany.objects.create(code='jmix', name='JMIX')
    return AccountJournal.create({'name': 'Diario JMX', 'code': 'JMX',
                                  'type': 'general',
                                  'company_id': company.pk})


def test_the_three_mixins_are_bases_in_the_source_order():
    mro = AccountJournal.__mro__
    positions = [mro.index(PortalMixin), mro.index(MailThread),
                 mro.index(MailActivityMixin)]
    assert positions == sorted(positions)


def test_a_message_is_posted_on_a_journal(journal):
    message = journal.message_post(body='Apertura del diario',
                                   notify=False)
    stored = MailMessage.objects.get(pk=message.pk)
    assert (stored.model, stored.res_id) == ('account.journal', journal.id)


def test_an_activity_is_scheduled_on_a_journal(journal):
    user = UserFactory()
    activity = journal.activity_schedule(summary='Revisar el diario',
                                         user=user)
    stored = MailActivity.objects.get(pk=activity.pk)
    assert (stored.res_model, stored.res_id) == ('account.journal',
                                                 journal.id)


def test_the_portal_token_is_written_once(journal):
    token = journal._portal_ensure_token()
    assert token
    assert AccountJournal.objects.filter(
        pk=journal.id, access_token=token).exists()
    assert journal._portal_ensure_token() == token


def test_the_inherit_list_is_the_source_one():
    assert AccountJournal.__dict__['_inherit'] == [
        'portal.mixin',
        'mail.alias.mixin.optional',
        'mail.thread',
        'mail.activity.mixin',
    ]
