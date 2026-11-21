"""``company_id`` de ``account.analytic.account`` con su default.

≙ ``company_id = fields.Many2one('res.company', default=lambda self:
self.env.company)``
(``odoo19c: addons/analytic/models/analytic_account.py:61``) y la moneda de
``currency_id`` (``:90``), que el puerto expone como ``currency``. Forma C
de ADR-029: el símbolo de la fuente sobre la columna de la fuente.

*Métrica:* el campo, su columna, el default por la empresa del entorno, la
moneda leída por él y la coherencia de ``clean`` con las líneas.
*Ciega a:* el ``check_company`` de ``partner_id`` y el resto de la paridad
de la etapa 1b.
"""
import pytest
from django.core.exceptions import ValidationError

from addons.analytic.models import (
    AccountAnalyticAccount, AccountAnalyticLine, AccountAnalyticPlan)
from addons.base.models.res_company import ResCompany
from orm.environments import env, set_current_company, sudo

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    company = ResCompany.objects.create(code='aci-a', name='ACI A')
    set_current_company(company.pk)
    yield company
    set_current_company(None)


@pytest.fixture
def plan():
    return AccountAnalyticPlan.objects.create(name='ACI Plan')


def test_the_company_field_has_the_source_name_and_column():
    field = AccountAnalyticAccount._meta.get_field('company_id')
    assert field.column == 'company_id'
    assert field.related_model is ResCompany
    assert field.null


def test_the_default_is_the_company_of_the_environment(company, plan):
    with sudo():
        [account] = env()['account.analytic.account'].create(
            [{'name': 'ACI Uno', 'plan_id': plan.pk}])
        assert account.company_id.pk == company.pk
        assert account.currency == company.currency


def test_without_an_active_company_the_account_is_shared(plan):
    set_current_company(None)
    with sudo():
        [account] = env()['account.analytic.account'].create(
            [{'name': 'ACI Compartida', 'plan_id': plan.pk}])
        assert not account.company_id
        assert account.currency is None


def test_clean_rejects_a_company_its_lines_do_not_share(company, plan):
    other = ResCompany.objects.create(code='aci-b', name='ACI B')
    account = AccountAnalyticAccount.objects.create(
        name='ACI Coherente', plan_id=plan, company_id=company)
    AccountAnalyticLine.objects.create(
        name='ACI Apunte', account=account, amount=1, company=company)
    account.company_id = other
    with sudo(), pytest.raises(ValidationError) as caught:
        account.clean()
    assert 'company_id' in caught.value.message_dict


def test_the_balances_sum_the_lines_of_a_basemodel_account(company, plan):
    """Regresión de la etapa 1a: el inverso ``lines`` de un ``BaseModel`` es
    un recordset, y ``credit``/``debit``/``balance`` sumaban con
    ``filter(...).aggregate``."""
    account = AccountAnalyticAccount.objects.create(
        name='ACI Saldos', plan_id=plan, company_id=company)
    for amount in (10, 5, -3):
        AccountAnalyticLine.objects.create(
            name='ACI Mov', account=account, amount=amount, company=company)
    with sudo():
        account = AccountAnalyticAccount.objects.get(pk=account.pk)
        assert account.credit == 15
        assert account.debit == 3
        assert account.balance == 12
