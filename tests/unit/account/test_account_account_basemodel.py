"""``account.account`` sobre ``BaseModel``, con ``placeholder_code``.

≙ ``odoo19c: addons/account/models/account_account.py:20-25, 41, 130-186,
355-377``: la cuenta es un modelo del ORM, su ``placeholder_code`` es el
código en la empresa activa o el de su primera empresa con el nombre de
ésta, y ``_order = 'code, placeholder_code'`` ordena por esa expresión.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.account.models import AccountAccount
from addons.base.models import ResCompany
from orm.environments import Environment, company_scope, sudo, user_scope
from orm.models import BaseModel

pytestmark = pytest.mark.django_db


@pytest.fixture
def parent_company():
    return ResCompany.objects.create(
        name='Matriz', code='kaupamex_test_u6_matriz')


@pytest.fixture
def other_company():
    return ResCompany.objects.create(
        name='Otra', code='kaupamex_test_u6_otra')


@pytest.fixture
def accountant(parent_company, other_company):
    """Un usuario con acceso a las dos empresas, como el de la fuente."""
    with sudo():
        user = get_user_model().objects.create_user(
            login='kaupamex-test-u6-accountant', password=None,
            name='Contable')
    user.company_ids.add(parent_company, other_company)
    return user


def _account(company, code='101000'):
    return AccountAccount.objects.create(
        code=code, name='Caja', account_type='asset_cash', company=company)


def test_the_account_is_a_basemodel():
    assert issubclass(AccountAccount, BaseModel)


def test_the_placeholder_is_the_code_in_the_active_company(
        parent_company, accountant):
    account = _account(parent_company)
    with user_scope(accountant.pk), company_scope(parent_company.pk):
        fresh = AccountAccount.objects.get(pk=account.pk)
        assert fresh.placeholder_code == '101000'


def test_the_placeholder_names_another_company(
    parent_company, other_company, accountant
):
    account = _account(parent_company)
    with user_scope(accountant.pk), company_scope(other_company.pk):
        fresh = AccountAccount.objects.get(pk=account.pk)
        assert fresh.placeholder_code == '101000 (Matriz)'


def test_the_order_uses_the_placeholder(
    parent_company, other_company, accountant
):
    foreign = _account(other_company)
    own = _account(parent_company)
    with user_scope(accountant.pk), company_scope(parent_company.pk), \
            Environment(uid=accountant.pk) as env:
        found = env['account.account'].search(
            [('id', 'in', [foreign.pk, own.pk])])
        assert found.ids == [own.pk, foreign.pk]
        assert found.mapped('placeholder_code') == [
            '101000', '101000 (Otra)']
