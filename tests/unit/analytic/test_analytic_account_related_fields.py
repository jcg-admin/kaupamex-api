"""``root_plan_id`` y ``color`` de ``account.analytic.account``.

≙ ``odoo19c: addons/analytic/models/analytic_account.py:44-53``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
analytic-account-related-fields.md``.

*Métrica:* el valor leído, la columna escrita y la búsqueda.
*Ciega a:* el uso de ``root_plan_id`` en ``get_relevant_plans`` (etapa D-2).
"""
import pytest
from django.db import connection

from addons.base.models import ResCompany
from orm.environments import env, set_current_company, sudo

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _context():
    with sudo():
        company = ResCompany.objects.create(name='Raíz de plan')
        set_current_company(company.pk)
        yield
        set_current_company(None)


def _plan(name, parent=None):
    vals = {'name': name}
    if parent is not None:
        vals['parent_id'] = parent.id
    return env()['account.analytic.plan'].create(vals)


def _account(plan):
    return env()['account.analytic.account'].create(
        {'name': 'Cuenta', 'plan_id': plan.id})


def test_the_root_plan_is_stored_in_its_column():
    root = _plan('Raíz')
    account = _account(_plan('Hijo', root))
    assert account.root_plan_id == root
    env().flush_all()
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT root_plan_id FROM account_analytic_account WHERE id = %s',
            [account.id])
        assert cursor.fetchone()[0] == root.id


def test_moving_the_plan_recomputes_the_root():
    root, other = _plan('Raíz'), _plan('Otra')
    child = _plan('Hijo', root)
    account = _account(child)
    child.write({'parent_id': other.id})
    assert account.root_plan_id == other


def test_the_root_plan_is_searchable():
    root = _plan('Raíz')
    account = _account(_plan('Hijo', root))
    found = env()['account.analytic.account'].search(
        [('root_plan_id', '=', root.id)])
    assert account.id in found.ids


def test_the_color_follows_the_plan():
    plan = _plan('Color')
    plan.write({'color': 7})
    assert _account(plan).color == 7
