"""``plan_id`` de ``account.analytic.account`` y su inverso ``account_ids``.

≙ ``plan_id = fields.Many2one('account.analytic.plan', required=True,
index=True)`` (``odoo19c: addons/analytic/models/analytic_account.py:38``)
y ``account_ids = fields.One2many('account.analytic.account', 'plan_id')``
(``odoo19c: addons/analytic/models/analytic_plan.py:58``), que alimenta
``account_count`` (``:148-150``). Forma C de ADR-029: el símbolo de la
fuente sobre la columna de la fuente.

*Métrica:* el campo, su columna, el inverso, ``account_count`` y el alta y
la búsqueda por ``plan_id`` en el ORM.
*Ciega a:* el resto de la paridad de campos de la etapa 1b.
"""
import pytest

from addons.analytic.models import AccountAnalyticAccount, AccountAnalyticPlan
from orm.environments import env, sudo

pytestmark = pytest.mark.django_db


def test_the_plan_field_has_the_source_name_and_column():
    field = AccountAnalyticAccount._meta.get_field('plan_id')
    assert field.column == 'plan_id'
    assert field.related_model is AccountAnalyticPlan
    assert not field.null


def test_the_plan_inverse_is_account_ids_and_feeds_the_count():
    plan = AccountAnalyticPlan.objects.create(name='PID Plan')
    with sudo():
        first, second = env()['account.analytic.account'].create([
            {'name': 'PID Uno', 'plan_id': plan.pk},
            {'name': 'PID Dos', 'plan_id': plan.pk},
        ])
        assert first.plan_id.pk == plan.pk
        assert env()['account.analytic.account'].search(
            [('plan_id', '=', plan.pk)]) == first | second
        assert set(plan.account_ids.ids) == {first.id, second.id}
        assert plan.account_count == 2


def test_the_default_order_follows_the_plan_by_id():
    """``_order = 'plan_id, name asc'`` (``analytic_account.py:15``): el
    orden del plan es su ``_order``, ``'sequence asc, id'``
    (``odoo19c: addons/analytic/models/analytic_plan.py:18``); con la misma
    secuencia decide el ``id``."""
    first_plan = AccountAnalyticPlan.objects.create(name='PID Zeta')
    second_plan = AccountAnalyticPlan.objects.create(name='PID Alfa')
    with sudo():
        later, earlier = env()['account.analytic.account'].create([
            {'name': 'PID A', 'plan_id': second_plan.pk},
            {'name': 'PID Z', 'plan_id': first_plan.pk},
        ])
        found = env()['account.analytic.account'].search(
            [('plan_id', 'in', [first_plan.pk, second_plan.pk])])
    assert list(found.ids) == [earlier.id, later.id]
