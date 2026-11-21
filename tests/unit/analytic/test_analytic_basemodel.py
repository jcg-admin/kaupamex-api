"""``account.analytic.account`` y ``account.analytic.line`` como
``BaseModel`` (etapa 1a del diseño).

≙ el programa ``basemodel-adoption-0397``: todo modelo con ``_name`` es un
``BaseModel`` (``odoo19c: odoo/orm/models.py:334``, ``:7046``, ``:7049``).
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
analytic-cluster.md``.

*Métrica:* la clase, el recordset de ``env[...]`` y un alta y una búsqueda
por el ORM de cada modelo.
*Ciega a:* la paridad de campos (etapa 1b) y las columnas por plan (etapa 2).
"""
import pytest

from addons.analytic.models import (
    AccountAnalyticAccount, AccountAnalyticLine, AccountAnalyticPlan)
from addons.base.models.res_company import ResCompany
from orm.environments import env, sudo
from orm.models import BaseModel

pytestmark = pytest.mark.django_db


def test_both_models_are_basemodels():
    assert issubclass(AccountAnalyticAccount, BaseModel)
    assert issubclass(AccountAnalyticLine, BaseModel)


def test_an_account_and_a_line_go_through_the_orm():
    # ``account.analytic.plan`` sigue siendo un modelo de Django: se crea
    # por su gestor.
    plan = AccountAnalyticPlan.objects.create(name='ABM Plan')
    # El default de ``company_id`` (``self.env.company``) es paridad de
    # campos: etapa 1b. Aquí la empresa se pasa explícita.
    company = ResCompany.objects.create(code='abm-1a', name='ABM')
    with sudo():
        [account] = env()['account.analytic.account'].create(
            [{'name': 'ABM Cuenta', 'plan': plan.pk}])
        [line] = env()['account.analytic.line'].create(
            [{'name': 'ABM Apunte', 'account': account.id, 'amount': 5,
              'company': company.pk}])
        assert env()['account.analytic.line'].search(
            [('account', '=', account.id)]) == line
        assert line.account == account
