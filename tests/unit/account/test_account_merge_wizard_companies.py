"""``account.merge.wizard._check_access_rights`` compara empresas de cuenta.

≙ ``odoo19c: addons/account/wizard/account_merge_wizard.py:125-132``: la
fusión se rehúsa si las ``company_ids`` de las cuentas incluyen una empresa
que el usuario no alcanza, y el mensaje nombra esa empresa
(``designs/account-account-mc2c.md``, MC2c-2).
"""
import pytest
from django.contrib.auth import get_user_model

from addons.account.models import AccountAccount
from addons.account.wizard.account_merge_wizard import AccountMergeWizard
from addons.base.models import ResCompany
from exceptions import UserError
from orm.commands import Command
from orm.environments import company_scope, sudo

pytestmark = pytest.mark.django_db


@pytest.fixture
def parent_company():
    return ResCompany.objects.create(
        name='Matriz', code='kaupamex_test_mc2c2_matriz')


@pytest.fixture
def branch_company(parent_company):
    return ResCompany.objects.create(
        name='Sucursal', code='kaupamex_test_mc2c2_sucursal',
        parent=parent_company)


@pytest.fixture
def shared_account(parent_company, branch_company):
    with sudo(), company_scope(parent_company.pk):
        return AccountAccount.create([{
            'name': 'Caja', 'code': '101000', 'account_type': 'asset_cash',
            'company_ids': [Command.set(
                [parent_company.pk, branch_company.pk])],
        }])


def _user(login, companies):
    with sudo():
        user = get_user_model().objects.create_user(
            login=login, password=None, name=login)
    user.company_ids.add(*companies)
    return user


def test_a_user_missing_one_company_is_refused_naming_it(
        parent_company, branch_company, shared_account):
    user = _user('kaupamex-test-mc2c2-partial', [parent_company])
    with pytest.raises(UserError, match='Sucursal'):
        AccountMergeWizard._check_access_rights(shared_account, user=user)


def test_a_user_reaching_every_company_passes(
        parent_company, branch_company, shared_account):
    user = _user('kaupamex-test-mc2c2-full', [parent_company, branch_company])
    assert AccountMergeWizard._check_access_rights(
        shared_account, user=user) == shared_account
