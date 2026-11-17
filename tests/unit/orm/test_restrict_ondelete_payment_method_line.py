"""Línea de método de pago: el método se protege y el diario se anula.

Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
restrict-ondelete-payment-method-line.md`` (tramo B). En la fuente
``payment_method_id`` es requerido sin ``ondelete`` (``restrict``) y
``journal_id`` no lo es (``set null``)
(``odoo19c: addons/account/models/account_payment_method.py:104-121``);
``AccountPaymentMethod.unlink`` borra antes sus líneas (``:90-92``).
"""
import pytest
from django.apps import apps
from django.db import models

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
    company = ResCompany.objects.create(code='pml-b', name='PML B')
    return AccountJournal.objects.create(
        name='Banco B', code='BNKB', type='bank', company=company)


@pytest.fixture
def method():
    return AccountPaymentMethod.objects.create(
        name='Tramo B', code='tramo_b', payment_type='inbound')


def test_unlink_of_the_method_removes_its_lines_first(method, journal):
    line = AccountPaymentMethodLine.objects.create(
        payment_method=method, journal=journal)
    method.unlink()
    assert not AccountPaymentMethod.objects.filter(pk=method.pk).exists()
    assert not AccountPaymentMethodLine.objects.filter(pk=line.pk).exists()


def test_a_raw_delete_of_a_method_with_lines_is_protected(method, journal):
    AccountPaymentMethodLine.objects.create(
        payment_method=method, journal=journal)
    with pytest.raises(models.ProtectedError):
        AccountPaymentMethod.objects.filter(pk=method.pk).delete()


def test_deleting_the_journal_keeps_the_line_without_journal(method,
                                                             journal):
    line = AccountPaymentMethodLine.objects.create(
        payment_method=method, journal=journal)
    AccountJournal.objects.filter(pk=journal.pk).delete()
    line.refresh_from_db()
    assert line.journal_id is None
