"""Los métodos manuales por defecto y el dominio de diarios elegibles.

Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
payment-method-defaults.md``. Referencia: los registros
``account_payment_method_manual_in``/``_out``
(``odoo19c: addons/account/data/account_data.xml:129-138``) y
``_get_payment_method_domain``
(``odoo19c: addons/account/models/account_payment_method.py:40-61``).
"""
import pytest
from django.apps import apps as django_apps
from django.db import connection

from addons.account.data.payment_methods import (
    MANUAL_PAYMENT_METHODS,
    seed_manual_payment_methods,
)
from addons.base.models import ResCompany
from orm.domains import Domain
from orm.environments import sudo
from orm.models import filtered_domain

pytestmark = pytest.mark.django_db

AccountJournal = django_apps.get_model('account', 'AccountJournal')
AccountPaymentMethod = django_apps.get_model('account',
                                             'AccountPaymentMethod')
IrModelData = django_apps.get_model('base', 'IrModelData')


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


def _by_xmlid(name):
    # La suite vacía las filas sembradas por migración (h-api-337): cada
    # prueba siembra las suyas con la misma función que la migración.
    seed_manual_payment_methods(django_apps, connection.alias)
    row = IrModelData.objects.get(module='account', name=name)
    return AccountPaymentMethod.objects.get(pk=row.res_id)


@pytest.mark.parametrize('name, payment_type', [
    ('account_payment_method_manual_in', 'inbound'),
    ('account_payment_method_manual_out', 'outbound'),
])
def test_the_manual_methods_exist_with_their_external_id(name,
                                                         payment_type):
    method = _by_xmlid(name)
    assert (method.name, method.code, method.payment_type) == (
        'Manual Payment', 'manual', payment_type)


def test_seeding_twice_creates_nothing_new():
    seed_manual_payment_methods(django_apps, connection.alias)
    before = AccountPaymentMethod.objects.filter(code='manual').count()
    seed_manual_payment_methods(django_apps, connection.alias)
    assert AccountPaymentMethod.objects.filter(
        code='manual').count() == before == len(MANUAL_PAYMENT_METHODS)


def test_without_code_the_domain_is_true():
    assert AccountPaymentMethod()._get_payment_method_domain(
        False) == Domain.TRUE


def test_the_manual_domain_selects_bank_and_drops_general_journals():
    company = ResCompany.objects.create(code='pm-dom', name='PM Dom')
    bank = AccountJournal.objects.create(
        name='Banco D', code='BNKD', type='bank', company=company)
    general = AccountJournal.objects.create(
        name='Varios D', code='MISD', type='general', company=company)
    domain = AccountPaymentMethod()._get_payment_method_domain('manual')
    found = filtered_domain(
        AccountJournal.objects.filter(pk__in=[bank.pk, general.pk]), domain)
    assert [journal.pk for journal in found] == [bank.pk]
