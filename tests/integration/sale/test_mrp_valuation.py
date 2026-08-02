"""Tests — ``mrp`` valuation wiring (move_raw/finished + workorders).

Cubre el costo real de fabricación: la orden genera los movimientos de materia
prima y de terminado desde la BoM; al producir, el consumo de componentes se
valúa como salida y el terminado se recibe con costo = materia prima valuada +
mano de obra (workorders × costo/hora del centro de trabajo).
"""
from decimal import Decimal

import pytest

from addons.mrp.models import (
    MrpBom,
    MrpBomLine,
    MrpProduction,
    MrpProductionMove,
    MrpRoutingWorkcenter,
    MrpWorkcenter,
    MrpWorkorder,
)
from addons.mrp import services as mrp_services
from addons.stock.models import StockLocation, StockMove
from addons.stock_account import services as valuation
from addons.stock_account.models import ProductCosting, StockValuationLayer
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.integration


def _product(price='100.00'):
    return make_product(name='MRP', price=Decimal(price))


def _bom(product, **kwargs):
    return MrpBom.objects.create(
        product_tmpl=product.product_tmpl, product=product, **kwargs)


def _stock_and_prod_locations():
    stock = StockLocation.objects.create(name='WH/Stock', usage=StockLocation.USAGE_INTERNAL)
    prod = StockLocation.objects.create(name='WH/Production', usage=StockLocation.USAGE_PRODUCTION)
    return stock, prod


def _receive(product, qty, unit_cost, stock):
    """Recibe materia prima valuada en stock (proveedor → interno)."""
    ProductCosting.for_product(product, cost_method=ProductCosting.COST_AVERAGE)
    src = StockLocation.objects.create(name='Vendors', usage=StockLocation.USAGE_SUPPLIER)
    move = StockMove.objects.create(
        product=product, product_uom_qty=Decimal(qty), quantity=Decimal(qty),
        location=src, location_dest=stock,
    )
    valuation.value_move(move, unit_cost=Decimal(unit_cost))


def test_generate_moves_from_bom(db):
    finished = _product()
    leg = _product()
    top = _product()
    bom = _bom(finished, product_qty=Decimal('1'))
    MrpBomLine.objects.create(bom=bom, product=leg, product_qty=Decimal('4'), sequence=1)
    MrpBomLine.objects.create(bom=bom, product=top, product_qty=Decimal('1'), sequence=2)
    mo = MrpProduction.objects.create(product=finished, product_qty=Decimal('2'), bom=bom)
    stock, prod = _stock_and_prod_locations()
    mrp_services.generate_moves(mo, stock, prod)
    # 2 movimientos de materia prima + 1 de terminado.
    assert mo.move_raw_ids().count() == 2
    assert mo.move_finished_ids().count() == 1
    # qty de materia prima = componente × product_qty (4×2=8 patas, 1×2=2 tableros).
    raw_qtys = sorted(m.product_uom_qty for m in mo.move_raw_ids())
    assert raw_qtys == [Decimal('2.00'), Decimal('8.00')]
    assert mo.move_finished_ids().first().product_uom_qty == Decimal('2.00')


def test_produce_values_finished_at_raw_plus_labor(db):
    finished = _product()
    leg = _product()
    top = _product()
    stock, prod = _stock_and_prod_locations()
    # Materia prima en stock: 8 patas @ 10 = 80 ; 2 tableros @ 50 = 100 → 180.
    _receive(leg, '8', '10.00', stock)
    _receive(top, '2', '50.00', stock)
    bom = _bom(finished, product_qty=Decimal('1'))
    MrpBomLine.objects.create(bom=bom, product=leg, product_qty=Decimal('4'), sequence=1)
    MrpBomLine.objects.create(bom=bom, product=top, product_qty=Decimal('1'), sequence=2)
    mo = MrpProduction.objects.create(product=finished, product_qty=Decimal('2'), bom=bom)
    # Mano de obra: 1 workorder de 60 min en centro a 90/h = 90.
    wc = MrpWorkcenter.objects.create(name='Ensamble', costs_hour=Decimal('90.00'))
    MrpWorkorder.objects.create(
        production=mo, workcenter=wc, duration=Decimal('60'),
    )
    mrp_services.generate_moves(mo, stock, prod)
    mo.action_confirm()
    unit_cost = mrp_services.produce(mo)
    # Materia prima 180 + mano de obra 90 = 270 ; / 2 uds = 135.
    assert mo.labor_cost() == Decimal('90.00')
    assert unit_cost == Decimal('135.0000')
    assert mo.state == MrpProduction.STATE_DONE
    # El terminado quedó valuado a 135: la SVL de entrada del terminado.
    fin_move = mo.move_finished_ids().first()
    fin_layer = StockValuationLayer.objects.get(stock_move=fin_move, quantity__gt=0)
    assert fin_layer.unit_cost == Decimal('135.0000')
    assert fin_layer.value == Decimal('270.00')
    # La materia prima se descontó del stock (salidas valuadas).
    assert valuation._product_qty_svl(leg) == Decimal('0.00')


def test_workorder_labor_cost(db):
    finished = _product()
    mo = MrpProduction.objects.create(product=finished, product_qty=Decimal('1'))
    op_wc = MrpWorkcenter.objects.create(name='Corte', costs_hour=Decimal('120.00'))
    wo = MrpWorkorder.objects.create(
        production=mo, workcenter=op_wc, duration=Decimal('30'),
    )
    # 30 min = 0.5 h × 120 = 60.
    assert wo.labor_cost() == Decimal('60.00')
    assert mo.labor_cost() == Decimal('60.00')


def test_routing_operation_links_workcenter_and_bom(db):
    finished = _product()
    bom = _bom(finished, product_qty=Decimal('1'))
    wc = MrpWorkcenter.objects.create(name='Pintura', costs_hour=Decimal('60.00'))
    op = MrpRoutingWorkcenter.objects.create(
        name='Pintar', bom=bom, workcenter=wc, time_cycle=Decimal('15'), sequence=1,
    )
    assert op.workcenter == wc
    assert list(bom.operations.all()) == [op]
    assert op.time_cycle == Decimal('15.00')


def test_production_move_bridge_roles(db):
    finished = _product()
    comp = _product()
    stock, prod = _stock_and_prod_locations()
    bom = _bom(finished, product_qty=Decimal('1'))
    MrpBomLine.objects.create(bom=bom, product=comp, product_qty=Decimal('1'), sequence=1)
    mo = MrpProduction.objects.create(product=finished, product_qty=Decimal('1'), bom=bom)
    mrp_services.generate_moves(mo, stock, prod)
    raw_links = MrpProductionMove.objects.filter(production=mo, role=MrpProductionMove.ROLE_RAW)
    fin_links = MrpProductionMove.objects.filter(production=mo, role=MrpProductionMove.ROLE_FINISHED)
    assert raw_links.count() == 1
    assert fin_links.count() == 1
    # El movimiento de materia prima va de stock a producción; el terminado al revés.
    assert raw_links.first().move.location_dest.usage == StockLocation.USAGE_PRODUCTION
    assert fin_links.first().move.location.usage == StockLocation.USAGE_PRODUCTION
