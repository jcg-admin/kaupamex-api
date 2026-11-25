"""La cuenta guarda sus empresas y su código por empresa raíz.

≙ ``company_ids`` y ``code_store`` (``odoo19c:
addons/account/models/account_account.py:40, 97-99``) y el inverso de
``code`` que escribe en la raíz (``:344-355``). Desde MC2c-1 ``code`` no
tiene columna: el inverso escribe ``code_store`` en la raíz de la empresa
activa.
"""
import pytest

from addons.account.models import AccountAccount
from addons.base.models import ResCompany
from orm.commands import Command
from orm.environments import company_scope, env as current_env

pytestmark = pytest.mark.django_db


@pytest.fixture
def root():
    return ResCompany.objects.create(
        name='Matriz', code='kaupamex_test_mc1_root')


@pytest.fixture
def branch(root):
    return ResCompany.objects.create(
        name='Sucursal', code='kaupamex_test_mc1_branch', parent=root)


def _account(company, code='101000'):
    return current_env()['account.account'].sudo().create({
        'code': code,
        'name': 'Caja',
        'account_type': 'asset_cash',
        'company_ids': [Command.set([company.pk])],
    })


def _code_store(account):
    field = AccountAccount._meta.get_field('code_store')
    fresh = AccountAccount.objects.get(pk=account.pk)
    return field.raw_company_values(fresh)


def test_the_account_belongs_to_its_company(root):
    account = _account(root)
    assert list(AccountAccount.objects.get(pk=account.pk)
                .company_ids.values_list('pk', flat=True)) == [root.pk]


def test_the_code_is_stored_under_the_root_company(branch, root):
    account = _account(branch)
    assert _code_store(account) == {str(root.pk): '101000'}


def test_changing_the_code_rewrites_the_root_value(root):
    account = _account(root)
    with company_scope(root.pk):
        current_env()['account.account'].sudo().browse(account.id).write(
            {'code': '101001'})
    assert _code_store(account) == {str(root.pk): '101001'}
