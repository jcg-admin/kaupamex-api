"""``account.account.create`` resuelve las empresas de la cuenta.

≙ ``odoo19c: addons/account/models/account_account.py:97-99, 1011-1051``:
``company_ids`` es requerido con la empresa activa por defecto, y ``create``
pone la activa primero cuando está entre las pedidas o no se pidió ninguna, y
traduce ``prefix``/``code_digits`` al primer código libre
(``designs/account-account-mc2b.md``).
"""
import pytest
from django.contrib.auth import get_user_model

from addons.account.models import AccountAccount
from addons.base.models import ResCompany
from orm.commands import Command
from orm.environments import company_scope, sudo, user_scope

pytestmark = pytest.mark.django_db


@pytest.fixture
def parent_company():
    return ResCompany.objects.create(
        name='Matriz', code='kaupamex_test_mc2b_matriz')


@pytest.fixture
def other_company():
    return ResCompany.objects.create(
        name='Otra', code='kaupamex_test_mc2b_otra')


@pytest.fixture
def accountant(parent_company, other_company):
    with sudo():
        user = get_user_model().objects.create_user(
            login='kaupamex-test-mc2b-accountant', password=None,
            name='Contable')
    user.company_ids.add(parent_company, other_company)
    return user


def _create(values):
    with sudo():
        return AccountAccount.create([{
            'name': 'Caja', 'account_type': 'asset_cash', **values,
        }])


def _company_ids(account):
    return set(AccountAccount.objects.filter(pk=account.id).values_list(
        'company_ids', flat=True))


def test_the_active_company_comes_first(
        parent_company, other_company, accountant):
    with user_scope(accountant.pk), company_scope(parent_company.pk):
        account = _create({'code': '101000', 'company_ids': [
            Command.set([other_company.pk, parent_company.pk])]})
    row = AccountAccount.objects.get(pk=account.id)
    assert row.company_id == parent_company.pk
    assert _company_ids(account) == {parent_company.pk, other_company.pk}


def test_explicit_companies_without_the_active_one_are_kept(
        parent_company, other_company, accountant):
    with user_scope(accountant.pk), company_scope(parent_company.pk):
        account = _create({'code': '101000', 'company_ids': [
            Command.set([other_company.pk])]})
    row = AccountAccount.objects.get(pk=account.id)
    assert row.company_id == other_company.pk
    assert _company_ids(account) == {other_company.pk}


def test_without_companies_the_active_company_is_used(
        parent_company, accountant):
    with user_scope(accountant.pk), company_scope(parent_company.pk):
        account = _create({'code': '101000'})
    row = AccountAccount.objects.get(pk=account.id)
    assert row.company_id == parent_company.pk
    assert _company_ids(account) == {parent_company.pk}


def test_a_prefix_becomes_the_first_free_code(parent_company, accountant):
    with user_scope(accountant.pk), company_scope(parent_company.pk):
        _create({'code': '101001'})
        account = _create({'prefix': '1010', 'code_digits': 6})
    assert AccountAccount.objects.get(pk=account.id).code == '101002'
