"""Los lectores de ``crm_team_member_ids`` como recordset.

``crm.team`` y ``crm.team.member`` son ``BaseModel``: el One2many de miembros
es un recordset, como en la fuente, y estos sitios lo recorrían con
``.all()``. Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/
designs/basemodel-reverse-queryset.md``.

≙ ``_compute_assignment_max``
(``odoo19c: addons/crm/models/crm_team.py:47-50``),
``_compute_lead_all_assigned_month_count`` (``:70-74``),
``_action_assign_leads`` (``:222-253``) y ``_assign_and_convert_leads``
(``:553-687``).

*Métrica:* los dos cómputos y que las dos rutas de reparto recorran a los
miembros sin error sobre un equipo sin iniciativas.
*Ciega a:* el reparto efectivo de iniciativas entre miembros.
"""
import pytest
from django.contrib.auth import get_user_model

from orm.environments import env, sudo

pytestmark = pytest.mark.django_db


@pytest.fixture
def team():
    users = [get_user_model().objects.create_user(
        login=f'ctr-{n}@kaupamex.mx', password='Ctr12345!')
        for n in (1, 2)]
    with sudo():
        [team] = env()['crm.team'].create([{'name': 'CTR Equipo'}])
        env()['crm.team.member'].create([
            {'crm_team_id': team.id, 'user_id': users[0].pk,
             'assignment_max': 10},
            {'crm_team_id': team.id, 'user_id': users[1].pk,
             'assignment_max': 5},
        ])
    return team


def test_the_capacity_adds_the_members(team):
    with sudo():
        assert team.assignment_max == 15


def test_the_assigned_month_count_adds_the_members(team):
    with sudo():
        assert team.lead_all_assigned_month_count == 0


def test_the_member_assignment_walks_the_members(team):
    with sudo():
        result = type(team)._assign_and_convert_leads(team)
    # Se indexa por miembro y sólo con iniciativas asignadas (``:605``).
    assert result == {}


def test_the_team_assignment_walks_the_members(team):
    with sudo():
        type(team)._action_assign_leads(team)
