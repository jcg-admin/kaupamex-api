"""``account.analytic.applicability`` sobre ``BaseModel`` (etapa C).

≙ ``odoo19c: addons/analytic/models/analytic_plan.py:405-455`` y la
extensión de ``account`` (``odoo19c: addons/account/models/
account_analytic_plan.py:6-82``). Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/
analytic-applicability-basemodel.md``.

*Métrica:* la cabecera, los nombres de campo, el default de empresa y la
lectura de ``applicability_ids`` como recordset.
*Ciega a:* la caché de ``get_relevant_plans`` (etapa D-2).
"""
import pytest

from addons.analytic.models import AccountAnalyticApplicability
from addons.base.models import ResCompany
from orm.environments import env, set_current_company, sudo
from orm.models import BaseModel

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _elevated():
    with sudo():
        yield


@pytest.fixture
def company(db):
    company = ResCompany.objects.create(name='Aplicabilidad C')
    set_current_company(company.pk)
    yield company
    set_current_company(None)


def test_the_applicability_is_a_base_model_with_the_source_header():
    assert issubclass(AccountAnalyticApplicability, BaseModel)
    assert AccountAnalyticApplicability._name == (
        'account.analytic.applicability')
    assert AccountAnalyticApplicability._description == (
        "Analytic Plan's Applicabilities")
    assert AccountAnalyticApplicability._check_company_auto is True


def test_the_fields_carry_the_source_names():
    columns = {f.name: f.column
               for f in AccountAnalyticApplicability._meta.concrete_fields}
    assert columns['analytic_plan_id'] == 'analytic_plan_id'
    assert columns['company_id'] == 'company_id'
    assert columns['product_categ_id'] == 'product_categ_id'
    assert {'create_date', 'write_date', 'create_uid',
            'write_uid'} <= set(columns)


def test_the_company_defaults_to_the_active_one(company):
    rule = env()['account.analytic.applicability'].create({
        'business_domain': 'general', 'applicability': 'optional'})
    assert rule.company_id.id == company.pk


def test_the_plan_reads_its_rules_as_a_recordset(company):
    plan = env()['account.analytic.plan'].create({'name': 'Plan C'})
    rule = env()['account.analytic.applicability'].create({
        'analytic_plan_id': plan.id, 'business_domain': 'general',
        'applicability': 'mandatory'})
    assert plan.applicability_ids.ids == [rule.id]
    assert plan._get_applicability(
        business_domain='general', company_id=company.pk) == 'mandatory'
