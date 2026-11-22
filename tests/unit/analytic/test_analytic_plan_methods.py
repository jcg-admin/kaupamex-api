"""Etapa D-1 de ``account.analytic.plan``: los métodos sin columna dinámica.

≙ ``odoo19c: addons/analytic/models/analytic_plan.py:104-121``,
``:184-212``, ``:246-265`` y ``:277-282``, más la siembra del plan de
proyecto (``odoo19c: addons/analytic/data/analytic_data.xml:13-17``).
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
analytic-plan-methods.md``.

*Métrica:* lo que devuelve cada método y la excepción que levanta.
*Ciega a:* los métodos que crean o retiran columnas dinámicas (etapa D-2).
"""
import pytest

from addons.analytic.models import AccountAnalyticPlan
from addons.analytic.models.analytic_plan import AccountAnalyticApplicability
from addons.base.models import ResCompany, SystemParameter
from exceptions import UserError
from orm.environments import env, set_current_company, sudo
from orm.registry import clear_cache

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _elevated():
    with sudo():
        yield


@pytest.fixture(autouse=True)
def _company(db):
    """``default_applicability`` depende de la empresa: se escribe y se lee
    con una activa."""
    company = ResCompany.objects.create(name='Analítica D1')
    set_current_company(company.pk)
    yield company
    set_current_company(None)


def _plans():
    return env()['account.analytic.plan']


@pytest.fixture
def project_plan():
    # La fuente siembra el plan de proyecto con ``optional``
    # (``analytic_data.xml:16``); el campo no tiene default.
    plan = _plans().create({'name': 'Proyecto D1',
                            'default_applicability': 'optional'})
    SystemParameter.set_param('analytic.project_plan', str(plan.id))
    clear_cache()
    return plan


def test_the_migration_seeds_a_project_plan():
    value = SystemParameter.get_param('analytic.project_plan')
    assert value and _plans().browse(int(value)).exists()


def test_without_the_parameter_get_all_plans_refuses():
    SystemParameter.set_param('analytic.project_plan', '0')
    clear_cache()
    with pytest.raises(UserError):
        list(_plans()._get_all_plans())


def test_get_all_plans_splits_project_and_other_roots(project_plan):
    other = _plans().create({'name': 'Otro D1'})
    child = _plans().create({'name': 'Hijo D1', 'parent_id': other.id})
    project, others = _plans()._get_all_plans()
    assert project == project_plan
    assert other.id in others.ids
    assert child.id not in others.ids
    assert project_plan.id not in others.ids


def test_column_names(project_plan):
    other = _plans().create({'name': 'Otro D1'})
    child = _plans().create({'name': 'Hijo D1', 'parent_id': other.id})
    assert project_plan._strict_column_name() == 'account_id'
    assert other._strict_column_name() == f'x_plan{other.id}_id'
    assert child._column_name() == f'x_plan{other.id}_id'


def test_the_project_plan_cannot_get_a_parent(project_plan):
    with pytest.raises(UserError):
        project_plan._onchange_parent_id()


def test_the_actions_return_the_source_dicts(project_plan):
    accounts = project_plan.action_view_analytical_accounts()
    assert accounts['res_model'] == 'account.analytic.account'
    assert accounts['domain'] == [('plan_id', 'child_of', project_plan.id)]
    children = project_plan.action_view_children_plans()
    assert children['domain'] == [('parent_id', '=', project_plan.id)]
    assert children['context'] == {'default_parent_id': project_plan.id,
                                   'default_color': project_plan.color}


def test_applicability_forced_rule_and_default(project_plan):
    assert project_plan._get_applicability(applicability='mandatory') == (
        'mandatory')
    assert project_plan._get_applicability() == 'optional'
    AccountAnalyticApplicability.objects.create(
        analytic_plan_id=project_plan.id, business_domain='invoice',
        applicability='mandatory')
    assert project_plan._get_applicability(
        business_domain='invoice') == 'mandatory'
    assert project_plan._get_applicability(
        business_domain='bill') == 'optional'


def test_hierarchy_name(project_plan):
    child = _plans().create({'name': 'Hijo D1',
                             'parent_id': project_plan.id})
    assert child._hierarchy_name() == (1, 'x_account_id_1')


def test_a_new_root_plan_reaches_get_all_plans(project_plan):
    list(_plans()._get_all_plans())
    other = _plans().create({'name': 'Nuevo D1'})
    _project, others = _plans()._get_all_plans()
    assert other.id in others.ids


def test_the_class_keeps_the_source_name_mangling():
    assert hasattr(AccountAnalyticPlan,
                   '_AccountAnalyticPlan__get_all_plans')
