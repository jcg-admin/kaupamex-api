"""Los casos de ``One2manyCase`` sobre comandos y jerarquía — ≙ ``odoo19c:
odoo/addons/test_orm/tests/test_one2many.py``.

Cubre ``test_dont_write_the_existing_childs`` (:271), ``test_create_with_
commands`` (:281), ``test_reward_line_delete`` (:337) y ``test_parent_id``
(:433).

pendiente: los ``assertQueryCount`` de ``test_create_with_commands``; este
ORM no emite el mismo número de sentencias y el recuento se mide aparte.
Los demás casos de la clase (``creativework``, ``attachment``,
``partner.merge``, ``new``) esperan sus modelos.
"""

import pytest

from exceptions import MissingError
from orm.commands import Command

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_dont_write_the_existing_childs(env):
    """≙ :271 — ``Command.link`` sobre un hijo ya enlazado no lo reescribe:
    el ``write`` del hijo lanza si su nombre es ``A``."""
    parent = env['test_orm.model_parent_m2o'].create({
        'name': 'parent',
        'child_ids': [Command.create({'name': 'A'})],
    })
    a = parent.child_ids[0]
    parent.write({'child_ids': [Command.link(a.id), Command.create({'name': 'B'})]})
    assert sorted(parent.child_ids.mapped('name')) == ['A', 'B']


def test_create_with_commands(env):
    """≙ :281 — ``Command.set`` en ``create`` roba las líneas de otro pedido."""
    Order = env['test_orm.order']
    order = Order.create({
        'line_ids': [Command.create({'product': name}) for name in ('set', 'sept')],
    })
    line1, line2 = order.line_ids
    Order.create({'line_ids': [Command.set(line1.ids)]})

    order = Order.create({'line_ids': [Command.set(line1.ids)]})
    thief = Order.create({'line_ids': [Command.set((line1 + line2).ids)]})

    assert not Order.browse(order.ids).line_ids
    assert Order.browse(thief.ids).line_ids == line1 + line2


def test_reward_line_delete(env):
    """≙ :337 — borrar una línea que arrastra a su recompensa no rompe el
    ``link`` siguiente; enlazar a propósito una línea ausente sí es error."""
    order = env['test_orm.order'].create({
        'line_ids': [
            Command.create({'product': 'a'}),
            Command.create({'product': 'b'}),
            Command.create({'product': 'b', 'reward': True}),
        ],
    })
    line0, line1, line2 = order.line_ids
    order.write({
        'line_ids': [
            Command.link(line0.id),
            Command.delete(line1.id),
            Command.link(line2.id),
        ],
    })
    assert env['test_orm.order'].browse(order.ids).line_ids == line0
    with pytest.raises(MissingError):
        order.write({'line_ids': [Command.link(line0.id), Command.link(line1.id)]})


def test_parent_id(env):
    """≙ :433 — ``child_of`` sobre un One2many cuyo comodelo tiene un
    ``parent_id`` relacionado no se recursa sin fin, ni con un ciclo."""
    Team, Member = env['test_orm.team'], env['test_orm.team.member']
    team1 = Team.create({'name': 'ORM'})
    team2 = Team.create({'name': 'Bugfix', 'parent_id': team1.id})
    team3 = Team.create({'name': 'Support', 'parent_id': team2.id})
    Member.create({'name': 'Raphael', 'team_id': team1.id})
    member2 = Member.create({'name': 'Noura', 'team_id': team3.id})
    Member.create({'name': 'Ivan', 'team_id': team2.id})

    assert member2.id == member2.team_id.parent_id.id
    Team.search([('member_ids', 'child_of', member2.id)])

    team1.write({'parent_id': team1.id})
    Team.search([('id', 'parent_of', team1.id)])
    Team.search([('id', 'child_of', team1.id)])


def test_commands_on_a_declared_one2many(env):
    """Un ``fields.One2many(comodel, inverse)`` declarado —no el reverso de
    Django— interpreta los mismos comandos al crear y al escribir."""
    Discussion = env['test_orm.discussion']
    discussion = Discussion.create({
        'name': 'd',
        'messages': [Command.create({'name': 'm1'}),
                     Command.create({'name': 'm2'})],
    })
    m1, m2 = sorted(Discussion.browse(discussion.ids).messages,
                    key=lambda message: message.name)
    assert (m1.name, m2.name) == ('m1', 'm2')
    discussion.write({'messages': [Command.update(m1.id, {'name': 'x'}),
                                   Command.delete(m2.id)]})
    messages = Discussion.browse(discussion.ids).messages
    assert [message.name for message in messages] == ['x']
    assert not env['test_orm.message'].browse(m2.ids).exists()
