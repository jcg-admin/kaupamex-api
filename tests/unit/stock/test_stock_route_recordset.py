"""``stock.route`` con su identidad y sobre el recordset de la fuente.

≙ ``odoo19c: addons/stock/models/stock_location.py:517-591``: ``_name``,
``write`` que archiva las reglas de destino activo, ``copy_data`` con
«(copy)» y ``_check_company_consistency``.
"""

import pytest

from addons.base.models import ResCompany
from addons.stock.models import StockLocation, StockRoute, StockRule
from exceptions import ValidationError
from orm.models import BaseModel


@pytest.fixture
def route_data(db):
    company = ResCompany.objects.create(
        name='Kaupamex', code='kaupamex_test_route')
    route = StockRoute.objects.create(name='Ruta U6a')
    live = StockLocation.objects.create(name='Viva U6a', usage='internal')
    dead = StockLocation.objects.create(
        name='Archivada U6a', usage='internal', active=False)
    on_live = StockRule.objects.create(
        name='A viva', action=StockRule.ACTION_PULL, route=route,
        location_dest=live)
    on_dead = StockRule.objects.create(
        name='A archivada', action=StockRule.ACTION_PULL, route=route,
        location_dest=dead)
    return {'company': company, 'route': route,
            'on_live': on_live, 'on_dead': on_dead}


def test_route_declares_the_reference_identity(route_data):
    route = route_data['route']
    assert StockRoute._name == 'stock.route'
    assert StockRoute._description == 'Inventory Routes'
    assert isinstance(route, BaseModel)


def test_archiving_the_route_archives_rules_with_a_live_destination(
        route_data):
    route_data['route'].write({'active': False})
    assert not StockRule.objects.get(pk=route_data['on_live'].pk).active
    assert StockRule.objects.get(pk=route_data['on_dead'].pk).active
    assert not StockRoute.objects.get(pk=route_data['route'].pk).active


def test_copy_names_the_duplicate(route_data):
    duplicate = route_data['route'].copy()
    assert duplicate.name == 'Ruta U6a (copy)'
    assert duplicate.id != route_data['route'].id


def test_a_rule_of_another_company_breaks_consistency(route_data):
    other = ResCompany.objects.create(
        name='Otra', code='kaupamex_test_route_other')
    StockRule.objects.filter(pk=route_data['on_live'].pk).update(
        company=other)
    with pytest.raises(ValidationError):
        route_data['route'].write({'company': route_data['company']})
