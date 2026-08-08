"""Tests — addon ``stock`` (adaptación de Odoo ``stock``).

Cubre la máquina de movimientos de inventario: ubicaciones (usage +
bypass), existencias (quant on-hand/available), el ciclo del movimiento
(confirm → assign/reservar → done/aplicar quants), la transferencia
(picking validate) y las reglas de aprovisionamiento (rule.run MTS/MTO).
"""
from decimal import Decimal

import pytest

from addons.stock.models import (
    StockLocation,
    StockMove,
    StockPicking,
    StockQuant,
    StockRule,
)
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.integration


def _product(price='100.00'):
    return make_product(name='Prod', price=Decimal(price))


def _internal(name='WH/Stock'):
    return StockLocation.objects.create(name=name, usage=StockLocation.USAGE_INTERNAL)


def _supplier():
    return StockLocation.objects.create(name='Vendors', usage=StockLocation.USAGE_SUPPLIER)


def _customer():
    return StockLocation.objects.create(name='Customers', usage=StockLocation.USAGE_CUSTOMER)


def test_location_complete_name_and_bypass(db):
    parent = _internal('WH')
    child = StockLocation.objects.create(
        name='Stock', usage=StockLocation.USAGE_INTERNAL, location=parent,
    )
    assert child.complete_name() == 'WH/Stock'
    # Internas reservan; proveedor/cliente/inventario/producción no.
    assert child.should_bypass_reservation() is False
    assert _supplier().should_bypass_reservation() is True
    assert _customer().should_bypass_reservation() is True


def test_quant_on_hand_and_available(db):
    product = _product()
    loc = _internal()
    StockQuant.set_on_hand(product, loc, Decimal('10.00'))
    assert StockQuant.available_qty(product, loc) == Decimal('10.00')
    # Ubicación no-interna: disponibilidad "infinita" (bypass).
    assert StockQuant.available_qty(product, _supplier()) == Decimal('999999999.00')


def test_move_confirm_assign_done_updates_quants(db):
    product = _product()
    src = _internal('WH/Stock')
    dest = _customer()
    StockQuant.set_on_hand(product, src, Decimal('5.00'))
    move = StockMove.objects.create(
        name=product.name, product=product, product_uom_qty=Decimal('3.00'),
        location=src, location_dest=dest,
    )
    # draft → confirmed (sin orígenes pendientes).
    move._action_confirm()
    assert move.state == StockMove.STATE_CONFIRMED
    # confirmed → assigned: reserva 3 de los 5 disponibles.
    move._action_assign()
    assert move.state == StockMove.STATE_ASSIGNED
    assert move.quantity == Decimal('3.00')
    # assigned → done: descuenta del origen interno; destino cliente es sumidero.
    move._action_done()
    assert move.state == StockMove.STATE_DONE
    assert StockQuant.available_qty(product, src) == Decimal('2.00')


def test_move_partial_reservation_stays_confirmed(db):
    product = _product()
    src = _internal()
    dest = _customer()
    StockQuant.set_on_hand(product, src, Decimal('2.00'))
    move = StockMove.objects.create(
        product=product, product_uom_qty=Decimal('5.00'),
        location=src, location_dest=dest,
    )
    move._action_confirm()
    move._action_assign()
    # Sólo 2 disponibles < 5 demandados → reserva parcial, no assigned.
    assert move.quantity == Decimal('2.00')
    assert move.state == StockMove.STATE_CONFIRMED


def test_move_mto_chaining_waiting(db):
    product = _product()
    src = _supplier()
    mid = _internal('WH/Input')
    dest = _customer()
    # Movimiento origen (proveedor → interno) que abastece al destino.
    orig = StockMove.objects.create(
        product=product, product_uom_qty=Decimal('4.00'), location=src, location_dest=mid,
    )
    dest_move = StockMove.objects.create(
        product=product, product_uom_qty=Decimal('4.00'), location=mid, location_dest=dest,
    )
    dest_move.move_orig.add(orig)
    dest_move._action_confirm()
    # Con origen pendiente (no done) → waiting.
    assert dest_move.state == StockMove.STATE_WAITING


def test_picking_validate_cascades_moves(db):
    product = _product()
    src = _internal('WH/Stock')
    dest = _customer()
    StockQuant.set_on_hand(product, src, Decimal('8.00'))
    picking = StockPicking.objects.create(location=src, location_dest=dest)
    move = StockMove.objects.create(
        product=product, product_uom_qty=Decimal('6.00'),
        location=src, location_dest=dest, picking=picking,
    )
    picking.action_confirm()
    assert picking.name.startswith('WH/')
    assert move.picking_id == picking.id
    move.refresh_from_db()
    assert move.state == StockMove.STATE_CONFIRMED
    picking.action_assign()
    move.refresh_from_db()
    assert move.state == StockMove.STATE_ASSIGNED
    picking.button_validate()
    assert picking.state == StockPicking.STATE_DONE
    move.refresh_from_db()
    assert move.state == StockMove.STATE_DONE
    assert StockQuant.available_qty(product, src) == Decimal('2.00')


def test_rule_run_make_to_stock(db):
    product = _product()
    src = _internal('WH/Stock')
    dest = _customer()
    rule = StockRule.objects.create(
        name='Entrega', action=StockRule.ACTION_PULL,
        location_src=src, location_dest=dest, procure_method=StockRule.PROCURE_MTS,
    )
    move = rule.run(product, Decimal('7.00'))
    assert move.product_uom_qty == Decimal('7.00')
    assert move.location_id == src.id
    assert move.location_dest_id == dest.id
    # MTS sin orígenes → confirmed.
    assert move.state == StockMove.STATE_CONFIRMED


def test_rule_run_attaches_picking(db):
    product = _product()
    src = _internal()
    dest = _customer()
    picking = StockPicking.objects.create(location=src, location_dest=dest)
    rule = StockRule.objects.create(
        name='Salida', location_src=src, location_dest=dest,
    )
    move = rule.run(product, Decimal('2.00'), picking=picking)
    assert move.picking_id == picking.id
    assert picking.move_ids.count() == 1


def test_move_cancel_zeroes_reservation(db):
    product = _product()
    src = _internal()
    dest = _customer()
    StockQuant.set_on_hand(product, src, Decimal('5.00'))
    move = StockMove.objects.create(
        product=product, product_uom_qty=Decimal('3.00'), location=src, location_dest=dest,
    )
    move._action_confirm()
    move._action_assign()
    move._action_cancel()
    assert move.state == StockMove.STATE_CANCEL
    assert move.quantity == Decimal('0.00')
