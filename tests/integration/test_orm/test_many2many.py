"""Porte de ``odoo19c: odoo/addons/test_orm/tests/test_many2many.py``.

Revisión de referencia: ``odoo-tools@abe4040ec1``. Los modelos ``ship``,
``pirate`` y ``prisoner`` comparten la tabla del modelo ``crew``
(``test_orm_crew``), cada relación con su par de columnas.

**Adaptación declarada:** ``test_attachment_m2m_link`` y
``test_bypass_search_access`` se apoyan en ``ir.attachment``, en los modelos
``test_orm.attachment``/``attachment.host`` y en ``new_test_user``, que no
forman parte de este porte.
"""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def crew(env):
    ship = env['test_orm.ship'].create({'name': 'Colombus'})
    env['test_orm.prisoner'].create({'name': 'Brian', 'ship_ids': ship.ids})
    blackbeard = env['test_orm.pirate'].create(
        {'name': 'Black Beard', 'ship_ids': ship.ids})
    redbeard = env['test_orm.pirate'].create({'name': 'Red Beard'})
    return ship, blackbeard, redbeard


def test_not_in_relation(env, crew):
    ship, _, redbeard = crew
    pirates = env['test_orm.pirate'].search([('ship_ids', 'not in', ship.ids)])
    assert len(pirates) == 1
    assert pirates == redbeard


def test_not_in_relation_as_query(env, crew):
    _, _, redbeard = crew
    ship_ids = env['test_orm.ship']._search([('name', '=', 'Colombus')])
    pirates = env['test_orm.pirate'].search([('ship_ids', 'not in', ship_ids)])
    assert len(pirates) == 1
    assert pirates == redbeard


def test_both_relations_share_the_crew_table(env, crew):
    """Caso propio del Consumer: cada relación lee sólo su par de columnas."""
    ship, blackbeard, _ = crew
    shipmates = env['test_orm.ship'].browse(ship.ids)
    assert shipmates.pirate_ids.mapped('name') == ['Black Beard']
    assert shipmates.prisoner_ids.mapped('name') == ['Brian']
    assert env['test_orm.crew'].search_count([]) == 2
