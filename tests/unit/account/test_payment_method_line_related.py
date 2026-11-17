"""Los campos relacionados de ``account.payment.method.line``.

Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
payment-method-line-related.md``. Referencia
``odoo19c: addons/account/models/account_payment_method.py:122-129``:
``code``, ``payment_type``, ``company_id`` y ``default_account_id`` son
relacionados no almacenados. El dominio del diario filtra por
``payment_type`` (``odoo19c: addons/account/models/account_journal.py:
205-209``): tiene que traducirse a SQL.
"""
import pytest
from django.apps import apps
from django.db import connection

from addons.base.models import ResCompany
from orm.environments import sudo

pytestmark = pytest.mark.django_db

AccountJournal = apps.get_model('account', 'AccountJournal')
AccountPaymentMethod = apps.get_model('account', 'AccountPaymentMethod')
AccountPaymentMethodLine = apps.get_model('account',
                                          'AccountPaymentMethodLine')


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def journal():
    company = ResCompany.objects.create(code='pml-rel', name='PML Rel')
    return AccountJournal.objects.create(
        name='Banco R', code='BNKR', type='bank', company=company)


@pytest.fixture
def lines(journal):
    inbound = AccountPaymentMethod.objects.create(
        name='Entra', code='rel_in', payment_type='inbound')
    outbound = AccountPaymentMethod.objects.create(
        name='Sale', code='rel_out', payment_type='outbound')
    return (
        AccountPaymentMethodLine.objects.create(payment_method=inbound,
                                                journal=journal),
        AccountPaymentMethodLine.objects.create(payment_method=outbound,
                                                journal=journal),
    )


def test_the_related_values_follow_method_and_journal(lines, journal):
    inbound, _outbound = lines
    assert inbound.code == 'rel_in'
    assert inbound.payment_type == 'inbound'
    assert inbound.company_id == journal.company
    assert inbound.default_account_id == journal.default_account


def test_a_domain_on_payment_type_separates_the_lines(lines):
    inbound, outbound = lines
    found = AccountPaymentMethodLine.search(
        [('payment_type', '=', 'inbound'),
         ('id', 'in', [inbound.pk, outbound.pk])])
    assert list(found.ids) == [inbound.pk]


def test_the_related_fields_have_no_column():
    with connection.cursor() as cursor:
        columns = {column.name for column in
                   connection.introspection.get_table_description(
                       cursor, 'account_payment_method_line')}
    assert not {'code', 'payment_type', 'company_id',
                'default_account_id'} & columns
