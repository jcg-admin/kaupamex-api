"""Las líneas de método de pago de un diario: por defecto, disponibles y
enlazadas al crear un método.

Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
journal-payment-method-lines.md``. Referencia: ``inbound_`` y
``outbound_payment_method_line_ids`` con sus cómputos
(``odoo19c: addons/account/models/account_journal.py:205-233,462-504``),
``_get_available_payment_method_lines`` (``:1188-1203``) y
``AccountPaymentMethod.create`` con ``_auto_link_payment_methods``
(``odoo19c: addons/account/models/account_payment_method.py:20-38``).
"""
import pytest
from django.apps import apps as django_apps
from django.db import connection

from addons.account.data import seed_manual_payment_methods
from addons.base.models import ResCompany, ResPartnerBank
from orm.environments import sudo

pytestmark = pytest.mark.django_db

AccountJournal = django_apps.get_model('account', 'AccountJournal')
AccountPaymentMethod = django_apps.get_model('account',
                                             'AccountPaymentMethod')
AccountPaymentMethodLine = django_apps.get_model('account',
                                                 'AccountPaymentMethodLine')


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def manual():
    """Los métodos manuales; la suite vacía las filas de migración."""
    inbound, outbound = seed_manual_payment_methods(django_apps,
                                                    connection.alias)
    return inbound, outbound


@pytest.fixture
def company():
    return ResCompany.objects.create(code='jpml', name='JPML')


def _journal(company, code, journal_type):
    return AccountJournal.create({'name': f'Diario {code}', 'code': code,
                                  'type': journal_type,
                                  'company_id': company.pk})


def test_a_bank_journal_gets_one_manual_line_each_way(manual, company):
    inbound, outbound = manual
    journal = _journal(company, 'JB1', 'bank')
    assert [line.payment_method_id for line in
            journal.inbound_payment_method_line_ids] == [inbound.pk]
    assert [line.payment_method_id for line in
            journal.outbound_payment_method_line_ids] == [outbound.pk]
    journal.env.flush_all()
    # En la base: calcular un sentido no desenlaza las líneas del otro.
    stored = AccountPaymentMethodLine.objects.filter(journal=journal.pk)
    assert sorted(line.payment_method_id for line in stored) == sorted(
        [inbound.pk, outbound.pk])


def test_a_general_journal_gets_no_lines(manual, company):
    journal = _journal(company, 'JG1', 'general')
    assert not journal.inbound_payment_method_line_ids
    assert not journal.outbound_payment_method_line_ids


def test_the_available_lines_follow_the_payment_type(manual, company):
    inbound, _outbound = manual
    journal = _journal(company, 'JB2', 'bank')
    available = journal._get_available_payment_method_lines('inbound')
    assert [line.payment_method_id for line in available] == [inbound.pk]


def test_an_empty_journal_has_no_available_lines():
    assert not AccountJournal().browse(
        ())._get_available_payment_method_lines('inbound')


def test_creating_a_multi_method_links_it_to_eligible_journals(
        manual, company, monkeypatch):
    bank = _journal(company, 'JB3', 'bank')
    general = _journal(company, 'JG3', 'general')
    information = AccountPaymentMethod._get_payment_method_information

    def with_tst(self):
        return {**information(self),
                'tst_multi': {'mode': 'multi', 'type': ('bank',)}}

    monkeypatch.setattr(AccountPaymentMethod,
                        '_get_payment_method_information', with_tst)
    method = AccountPaymentMethod.create({'name': 'Tst', 'code': 'tst_multi',
                                          'payment_type': 'inbound'})
    linked = AccountPaymentMethodLine.objects.filter(payment_method=method)
    assert sorted(line.journal_id for line in linked) == [bank.pk]
    assert general.pk not in [line.journal_id for line in linked]


def test_unlinking_a_journal_removes_its_payment_method_lines(manual,
                                                              company):
    journal = _journal(company, 'JB4', 'bank')
    line_ids = [line.pk for line in
                journal.inbound_payment_method_line_ids
                | journal.outbound_payment_method_line_ids]
    assert line_ids
    journal.unlink()
    assert not AccountJournal.objects.filter(pk=journal.pk).exists()
    assert not AccountPaymentMethodLine.objects.filter(
        pk__in=line_ids).exists()


def _bank_account(company, number):
    return ResPartnerBank.objects.create(acc_number=number,
                                         partner=company.partner)


def test_unlink_removes_the_bank_account_only_it_used(manual, company):
    own = _bank_account(company, 'JPML-OWN')
    shared = _bank_account(company, 'JPML-SHARED')
    first = _journal(company, 'JB5', 'bank')
    second = _journal(company, 'JB6', 'bank')
    keeper = _journal(company, 'JB7', 'bank')
    first.write({'bank_account_id': own.pk})
    second.write({'bank_account_id': shared.pk})
    keeper.write({'bank_account_id': shared.pk})
    (first | second).unlink()
    assert not ResPartnerBank.objects.filter(pk=own.pk).exists()
    assert ResPartnerBank.objects.filter(pk=shared.pk).exists()
