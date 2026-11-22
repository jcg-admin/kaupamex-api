"""``account.analytic.plan`` sobre ``BaseModel`` (etapa A).

≙ la cabecera y los campos de ``odoo19c: addons/analytic/models/
analytic_plan.py:14-70`` y sus cómputos (``:129-182``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
analytic-plan-basemodel.md``.

*Métrica:* la cabecera, la columna de ``complete_name``, los valores que
calcula el ORM y la búsqueda por ``root_id``.
*Ciega a:* las columnas dinámicas por plan (etapa B) y la aplicabilidad
(etapa C).
"""
import pytest

from addons.analytic.models import AccountAnalyticPlan
from orm.environments import env, sudo
from orm.models import BaseModel

pytestmark = pytest.mark.django_db


def _plans():
    return env()['account.analytic.plan']


def test_the_plan_is_a_base_model_with_the_source_header():
    assert issubclass(AccountAnalyticPlan, BaseModel)
    assert AccountAnalyticPlan._name == 'account.analytic.plan'
    assert AccountAnalyticPlan._parent_store is True
    assert AccountAnalyticPlan._rec_name == 'complete_name'
    assert AccountAnalyticPlan._order == 'sequence asc, id'
    assert AccountAnalyticPlan._meta.get_field('parent_id').column == (
        'parent_id')


def test_the_complete_name_is_stored_and_follows_the_parent():
    with sudo():
        root = _plans().create({'name': 'Marketing'})
        child = _plans().create({'name': 'Digital', 'parent_id': root.id})
        grandchild = _plans().create({'name': 'SEM', 'parent_id': child.id})
        assert grandchild.complete_name == 'Marketing / Digital / SEM'
        root.write({'name': 'Mercadeo'})
        grandchild.invalidate_recordset()
        assert grandchild.complete_name == 'Mercadeo / Digital / SEM'
    assert AccountAnalyticPlan.objects.filter(pk=grandchild.id).values_list(
        'complete_name', flat=True).get() == 'Mercadeo / Digital / SEM'


def test_the_root_is_computed_and_searchable():
    with sudo():
        root = _plans().create({'name': 'Raíz'})
        child = _plans().create({'name': 'Rama', 'parent_id': root.id})
        leaf = _plans().create({'name': 'Hoja', 'parent_id': child.id})
        assert (root | child | leaf).mapped('root_id') == root
        assert _plans().search([('root_id', '=', root.id)]) == (
            root | child | leaf)


def test_the_counters_run_over_a_recordset():
    with sudo():
        first = _plans().create({'name': 'Uno'})
        second = _plans().create({'name': 'Dos'})
        _plans().create({'name': 'Uno A', 'parent_id': first.id})
        env()['account.analytic.account'].create([
            {'name': 'Cuenta 1', 'plan_id': first.id},
            {'name': 'Cuenta 2', 'plan_id': second.id},
            {'name': 'Cuenta 3', 'plan_id': second.id},
        ])
        plans = first | second
        assert plans.mapped('children_count') == [1, 0]
        assert plans.mapped('account_count') == [1, 2]
        assert plans.mapped('all_account_count') == [1, 2]


def test_moving_a_plan_updates_the_parent_path():
    with sudo():
        old_parent = _plans().create({'name': 'Origen'})
        new_parent = _plans().create({'name': 'Destino'})
        plan = _plans().create({'name': 'Móvil', 'parent_id': old_parent.id})
        plan.write({'parent_id': new_parent.id})
        assert plan.parent_path == f'{new_parent.id}/{plan.id}/'
        assert plan.complete_name == 'Destino / Móvil'
