"""``stock.move`` escribe y borra con la firma de recordset de la fuente.

≙ ``write(self, vals)`` y ``unlink(self)``
(``odoo19c: addons/stock/models/stock_move.py``). Antes eran métodos que
operaban sobre un solo movimiento y los Many2many se escribían con el gestor
de Django (``.add``); ahora un recordset de varios movimientos se escribe y
se borra de una vez, y los Many2many reciben comandos.
"""

from decimal import Decimal

import pytest

from addons.base.models import ResCompany
from addons.product.models import ProductProduct, ProductTemplate
from addons.stock.models import (
    StockLocation,
    StockMove,
    StockMoveLine,
    StockPicking,
    StockPickingType,
    StockQuant,
)
from addons.uom.models.uom_uom import Uom
from orm.commands import Command


@pytest.fixture
def moves(db):
    company = ResCompany.objects.create(
        name='Kaupamex', code='kaupamex_test_mvcrud')
    source = StockLocation.objects.create(
        name='Stock MVCRUD', usage='internal')
    destination = StockLocation.objects.create(
        name='Customers MVCRUD', usage='customer')
    uom = Uom.objects.create(name='Unidad MVCRUD')
    template = ProductTemplate.objects.create(
        name='Camisa MVCRUD', list_price=Decimal('100.00'),
        is_storable=True, uom_id=uom)
    variant = ProductProduct.objects.create(
        product_tmpl_id=template, default_code='CAM-MVCRUD')
    picking_type = StockPickingType.objects.create(
        name='Entrega MVCRUD', code='outgoing', sequence_code='OUTMVCRUD',
        company=company)
    picking = StockPicking.objects.create(
        name='OUT/MVCRUD', company=company, location=source,
        location_dest=destination, picking_type=picking_type)
    created = [
        StockMove.objects.create(
            picking=picking, product=variant, location=source,
            location_dest=destination, company=company, product_uom=uom,
            product_uom_qty=Decimal('5'))
        for _index in range(2)
    ]
    return created[0].browse([move.pk for move in created])


def test_write_applies_the_values_to_every_move(moves):
    moves.write({'priority': '1'})
    assert set(
        StockMove.objects.filter(pk__in=moves.ids).values_list(
            'priority', flat=True)) == {'1'}


def test_write_links_a_many2many_with_a_command(moves):
    origin, chained = moves
    chained.write({'move_orig_ids': [Command.link(origin.id)]})
    assert chained.move_orig_ids.ids == [origin.id]
    assert origin.move_dest_ids.ids == [chained.id]


def test_unlink_deletes_every_draft_move(moves):
    ids = moves.ids
    moves.unlink()
    assert not StockMove.objects.filter(pk__in=ids).exists()


def test_free_reservation_clears_the_origins_of_the_invaded_move(moves):
    """≙ ``odoo19c: addons/stock/models/stock_move_line.py:846-850``.

    El movimiento cuya reserva se invade pasa a ``make_to_stock`` y pierde
    sus orígenes con ``Command.clear()``.
    """
    invading, invaded = moves
    origin = invaded.copy()
    invaded.write({'move_orig_ids': [Command.link(origin.id)]})
    common = dict(
        product=invaded.product, location=invaded.location,
        location_dest=invaded.location_dest, company=invaded.company,
        product_uom=invaded.product_uom, picking=invaded.picking)
    reserved = StockMoveLine.objects.create(
        move=invaded, quantity=Decimal('2'), **common)
    forcing = StockMoveLine.objects.create(
        move=invading, quantity=Decimal('2'), **common)

    forcing._free_reservation(
        invaded.product, invaded.location, Decimal('2'))

    assert not StockMoveLine.objects.filter(pk=reserved.pk).exists()
    refreshed = StockMove.objects.get(pk=invaded.pk)
    assert refreshed.procure_method == StockMove.PROCURE_MAKE_TO_STOCK
    assert not refreshed.move_orig_ids


def test_quant_create_returns_a_recordset(moves):
    """``StockQuant.create`` devuelve el recordset de la fuente, no un
    ``QuerySet``: sobre éste ``.ids`` no existe."""
    move = moves[:1]
    quants = StockQuant.create([{
        'product': move.product, 'location': move.location,
        'company': move.company, 'quantity': Decimal('4')}])
    assert quants.ids == list(
        StockQuant.objects.filter(pk__in=quants.ids).values_list(
            'pk', flat=True))
    assert len(quants) == 1
