"""``account.code.mapping``: los códigos de una cuenta por empresa.

≙ ``odoo19c: addons/account/models/account_code_mapping.py``: un modelo sin
tabla cuyos registros se fabrican con el id ``account_id * 10000 +
company_id``. Leído desde ``account.account.code_mapping_ids`` da una fila
por empresa del usuario con el código de la cuenta en esa empresa; escribir
su ``code`` lo guarda en esa empresa; buscarlo sin cuenta rehúsa
(``designs/account-code-mapping.md``).
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import ResCompany
from exceptions import UserError
from orm.commands import Command
from orm.environments import (
    company_scope, env as current_env, sudo, user_scope)

pytestmark = pytest.mark.django_db

COMPANY_OFFSET = 10000


@pytest.fixture
def first_company():
    return ResCompany.objects.create(
        name='Primera', code='kaupamex_test_mapping_first')


@pytest.fixture
def second_company():
    return ResCompany.objects.create(
        name='Segunda', code='kaupamex_test_mapping_second')


@pytest.fixture
def accountant(first_company, second_company):
    with sudo():
        user = get_user_model().objects.create_user(
            login='kaupamex-test-mapping-accountant', password=None,
            name='Contable')
    user.company_ids.add(first_company, second_company)
    return user


@pytest.fixture
def shared_account(first_company, second_company):
    """Una cuenta en dos empresas raíz, con un código en cada una."""
    with sudo(), company_scope(first_company.pk):
        account = current_env()['account.account'].sudo().create({
            'name': 'Caja', 'code': '101000', 'account_type': 'asset_cash',
            'company_ids': [Command.set([first_company.pk])],
        })
    with sudo(), company_scope(second_company.pk):
        # El código en la segunda empresa viaja en la misma escritura que la
        # empresa: ``_ensure_code_is_unique`` exige uno por empresa.
        account.write({'code': '101900',
                       'company_ids': [Command.link(second_company.pk)]})
    return account


def test_each_company_of_the_user_gets_a_mapping_with_its_code(
        shared_account, first_company, second_company, accountant):
    with user_scope(accountant.pk), company_scope(first_company.pk):
        mappings = shared_account.code_mapping_ids
        rows = {(mapping.company_id.id, mapping.code) for mapping in mappings}
    assert rows == {(first_company.pk, '101000'),
                    (second_company.pk, '101900')}
    assert {mapping.id for mapping in mappings} == {
        shared_account.id * COMPANY_OFFSET + first_company.pk,
        shared_account.id * COMPANY_OFFSET + second_company.pk,
    }


def test_writing_a_mapping_code_stores_it_in_that_company(
        shared_account, first_company, second_company, accountant):
    with user_scope(accountant.pk), company_scope(first_company.pk):
        mapping = current_env()['account.code.mapping'].browse(
            shared_account.id * COMPANY_OFFSET + second_company.pk)
        mapping.write({'code': '101950'})
    with sudo(), company_scope(second_company.pk):
        shared_account.invalidate_recordset(fnames=['code'])
        assert shared_account.code == '101950'
    with sudo(), company_scope(first_company.pk):
        shared_account.invalidate_recordset(fnames=['code'])
        assert shared_account.code == '101000'


def test_searching_without_an_account_is_refused(accountant, first_company):
    with user_scope(accountant.pk), company_scope(first_company.pk):
        with pytest.raises(UserError, match='cannot be accessed directly'):
            current_env()['account.code.mapping'].search([])
