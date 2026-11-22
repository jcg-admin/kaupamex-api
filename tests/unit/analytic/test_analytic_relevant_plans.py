"""Etapa D-2a: ``get_relevant_plans`` y su caché por cursor.

≙ ``odoo19c: addons/analytic/models/analytic_plan.py:214-244``, con los
vaciados de ``:272-275``, ``:372-379`` y ``:433-443``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
analytic-relevant-plans.md``.

*Métrica:* la lista devuelta y el contenido de ``env.cr.cache``.
*Ciega a:* las columnas dinámicas (etapa B).
"""
import pytest

from addons.base.models import ResCompany, SystemParameter
from orm.environments import env, set_current_company, sudo
from orm.registry import clear_cache

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _context():
    with sudo():
        company = ResCompany.objects.create(name='Planes relevantes')
        set_current_company(company.pk)
        env().cr.cache.pop('get_relevant_plans', None)
        yield company
        set_current_company(None)


def _plans():
    return env()['account.analytic.plan']


def _account(plan):
    return env()['account.analytic.account'].create(
        {'name': f'Cuenta {plan.name}', 'plan_id': plan.id})


@pytest.fixture
def project():
    plan = _plans().create({'name': 'Proyecto D2',
                            'default_applicability': 'optional'})
    SystemParameter.set_param('analytic.project_plan', str(plan.id))
    clear_cache()
    _account(plan)
    return plan


def _ids(result):
    return [row['id'] for row in result]


def test_a_root_plan_with_accounts_is_relevant(project):
    empty = _plans().create({'name': 'Vacío D2',
                             'default_applicability': 'optional'})
    result = _plans().get_relevant_plans()
    assert project.id in _ids(result)
    assert empty.id not in _ids(result)
    row = next(r for r in result if r['id'] == project.id)
    assert row['applicability'] == 'optional'
    assert row['column_name'] == 'account_id'
    assert row['all_account_count'] == 1


def test_an_unavailable_plan_is_forced_by_a_chosen_account(project):
    hidden = _plans().create({'name': 'Oculto D2',
                              'default_applicability': 'unavailable'})
    account = _account(hidden)
    assert hidden.id not in _ids(_plans().get_relevant_plans())
    forced = _plans().get_relevant_plans(existing_account_ids=[account.id])
    row = next(r for r in forced if r['id'] == hidden.id)
    assert row['applicability'] == 'optional'


def test_the_second_call_comes_from_the_cursor_cache(project):
    first = _plans().get_relevant_plans()
    assert _plans().get_relevant_plans() is first
    assert env().cr.cache['get_relevant_plans']


def test_creating_a_plan_clears_the_cache(project):
    _plans().get_relevant_plans()
    _plans().create({'name': 'Nuevo D2'})
    assert 'get_relevant_plans' not in env().cr.cache


def test_changing_the_default_applicability_clears_the_cache(project):
    _plans().get_relevant_plans()
    project.write({'default_applicability': 'mandatory'})
    assert 'get_relevant_plans' not in env().cr.cache


def test_touching_a_rule_clears_the_cache(project):
    _plans().get_relevant_plans()
    env()['account.analytic.applicability'].create({
        'analytic_plan_id': project.id, 'business_domain': 'general',
        'applicability': 'mandatory'})
    assert 'get_relevant_plans' not in env().cr.cache
