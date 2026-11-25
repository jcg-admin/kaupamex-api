"""``code`` se calcula sobre ``code_store`` en la raíz de la empresa activa.

≙ ``code`` calculado con búsqueda e inverso y su rama de ``_field_to_sql``
(``odoo19c: addons/account/models/account_account.py:39, 131-132,
333-353``), y el ``create`` que fija las empresas de la cuenta como activas
(``:1042-1047``). ``designs/account-account-mc2c.md``, MC2c-1.
"""
import pytest

from addons.account.models import AccountAccount
from addons.base.models import ResCompany
from orm.commands import Command, related_manager
from orm.environments import company_scope, env as current_env

pytestmark = pytest.mark.django_db


@pytest.fixture
def root():
    return ResCompany.objects.create(
        name='Matriz', code='kaupamex_test_mc2c1_root')


@pytest.fixture
def branch(root):
    return ResCompany.objects.create(
        name='Sucursal', code='kaupamex_test_mc2c1_branch', parent=root)


@pytest.fixture
def other():
    return ResCompany.objects.create(
        name='Otra', code='kaupamex_test_mc2c1_other')


def _account(company, code='101000'):
    return current_env()['account.account'].sudo().create({
        'code': code,
        'name': 'Caja',
        'account_type': 'asset_cash',
        'company_ids': [Command.set([company.pk])],
    })


def _code_store(account):
    field = AccountAccount._meta.get_field('code_store')
    return field.raw_company_values(AccountAccount.objects.get(pk=account.id))


def test_the_code_is_read_at_the_root_of_the_active_company(branch):
    account = _account(branch)
    # Sin la caché del alta: el valor sale del cálculo, no de lo escrito.
    current_env().invalidate_all()
    with company_scope(branch.pk):
        fresh = current_env()['account.account'].sudo().browse(account.id)
        assert fresh.code == '101000'


def test_create_stores_the_code_under_the_account_company_root(
        root, other):
    with company_scope(root.pk):
        account = _account(other)
    assert _code_store(account) == {str(other.pk): '101000'}


def test_writing_the_code_rewrites_the_root_value(branch, root):
    account = _account(branch)
    with company_scope(branch.pk):
        current_env()['account.account'].sudo().browse(account.id).write(
            {'code': '101001'})
    assert _code_store(account) == {str(root.pk): '101001'}


def test_the_code_is_searched_at_the_root_of_the_active_company(branch):
    account = _account(branch)
    _account(branch, code='102000')
    with company_scope(branch.pk):
        found = current_env()['account.account'].sudo().search(
            [('code', '=', '101000')])
    assert found.ids == [account.id]


def test_the_order_follows_the_code_of_the_active_company(branch):
    second = _account(branch, code='102000')
    first = _account(branch, code='101000')
    with company_scope(branch.pk):
        found = current_env()['account.account'].sudo().search(
            [('id', 'in', [first.id, second.id])])
    assert found.ids == [first.id, second.id]


@pytest.fixture
def shared(root, other):
    """Una cuenta de dos empresas con un código distinto en cada raíz."""
    account = _account(root)
    row = AccountAccount.objects.get(pk=account.id)
    field = AccountAccount._meta.get_field('code_store')
    field.set_for_company(row, other.pk, '201000')
    row.save(update_fields=['code_store'])
    related_manager(row, "company_ids").add(other)
    return account


def test_each_company_reads_its_own_code(shared, root, other):
    with company_scope(other.pk):
        assert current_env()['account.account'].sudo().browse(
            shared.id).code == '201000'
    with company_scope(root.pk):
        assert current_env()['account.account'].sudo().browse(
            shared.id).code == '101000'


def test_each_company_searches_its_own_code(shared, other):
    with company_scope(other.pk):
        found = current_env()['account.account'].sudo().search(
            [('code', '=', '201000')])
    assert found.ids == [shared.id]
