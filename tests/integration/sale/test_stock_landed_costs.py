"""Tests — addon ``stock_landed_costs`` (costes en destino).

Cubre el **costo unitario real de entrega**: un flete/arancel se reparte sobre
los productos recibidos (por cantidad, por costo, igual, por peso) y se suma a
su valoración, subiendo el costo promedio del producto.
"""
from decimal import Decimal

import pytest

from addons.catalogue.models import Product
from addons.stock.models import StockLocation, StockMove
from addons.stock_account import services as valuation
from addons.stock_account.models import ProductCosting, StockValuationLayer
from addons.stock_landed_costs import services as landed
from addons.stock_landed_costs.models import (
    StockLandedCost,
    StockLandedCostLine,
    StockValuationAdjustment,
)

pytestmark = pytest.mark.integration

_slug_seq = [0]


def _product(price='100.00', weight='1.00'):
    _slug_seq[0] += 1
    n = _slug_seq[0]
    return Product.objects.create(
        name=f'LC {n}', slug=f'lc-prod-{n}', sku=f'LC-{n:04d}',
        price=Decimal(price), weight_kg=Decimal(weight),
    )


def _receipt(product, qty, unit_cost, cost_method=ProductCosting.COST_AVERAGE):
    """Recibe ``qty`` de ``product`` a ``unit_cost`` y devuelve el StockMove."""
    ProductCosting.for_product(product, cost_method=cost_method)
    src = StockLocation.objects.create(name='Vendors', usage=StockLocation.USAGE_SUPPLIER)
    dest = StockLocation.objects.create(name='WH', usage=StockLocation.USAGE_INTERNAL)
    move = StockMove.objects.create(
        product=product, product_uom_qty=Decimal(qty), quantity=Decimal(qty),
        location=src, location_dest=dest,
    )
    valuation.value_move(move, unit_cost=Decimal(unit_cost))
    return move


def test_landed_cost_by_quantity_split(db):
    pa = _product()
    pb = _product()
    ma = _receipt(pa, '10', '100.00')   # 10 uds
    mb = _receipt(pb, '30', '100.00')   # 30 uds → total 40
    lc = StockLandedCost.objects.create(name='Flete')
    StockLandedCostLine.objects.create(
        cost=lc, name='Flete', price_unit=Decimal('400.00'),
        split_method=StockLandedCostLine.SPLIT_BY_QUANTITY,
    )
    landed.compute(lc, [ma, mb])
    adj_a = StockValuationAdjustment.objects.get(cost=lc, move=ma)
    adj_b = StockValuationAdjustment.objects.get(cost=lc, move=mb)
    # 400 repartido por cantidad: 10/40*400=100 ; 30/40*400=300.
    assert adj_a.additional_landed_cost == Decimal('100.00')
    assert adj_b.additional_landed_cost == Decimal('300.00')
    assert adj_a.final_cost == Decimal('1100.00')  # former 1000 + 100


def test_landed_cost_equal_split(db):
    pa = _product()
    pb = _product()
    ma = _receipt(pa, '10', '100.00')
    mb = _receipt(pb, '30', '100.00')
    lc = StockLandedCost.objects.create(name='Seguro')
    StockLandedCostLine.objects.create(
        cost=lc, price_unit=Decimal('300.00'),
        split_method=StockLandedCostLine.SPLIT_EQUAL,
    )
    landed.compute(lc, [ma, mb])
    # 300 / 2 movimientos = 150 cada uno.
    for m in (ma, mb):
        assert StockValuationAdjustment.objects.get(cost=lc, move=m).additional_landed_cost == Decimal('150.00')


def test_landed_cost_by_current_cost_split(db):
    pa = _product()
    pb = _product()
    ma = _receipt(pa, '10', '100.00')   # former 1000
    mb = _receipt(pb, '10', '300.00')   # former 3000 → total 4000
    lc = StockLandedCost.objects.create(name='Arancel')
    StockLandedCostLine.objects.create(
        cost=lc, price_unit=Decimal('800.00'),
        split_method=StockLandedCostLine.SPLIT_BY_COST,
    )
    landed.compute(lc, [ma, mb])
    # 800 por costo: 1000/4000*800=200 ; 3000/4000*800=600.
    assert StockValuationAdjustment.objects.get(cost=lc, move=ma).additional_landed_cost == Decimal('200.00')
    assert StockValuationAdjustment.objects.get(cost=lc, move=mb).additional_landed_cost == Decimal('600.00')


def test_landed_cost_by_weight_split(db):
    pa = _product(weight='2.00')
    pb = _product(weight='3.00')
    ma = _receipt(pa, '10', '100.00')   # peso 20
    mb = _receipt(pb, '10', '100.00')   # peso 30 → total 50
    lc = StockLandedCost.objects.create(name='Flete peso')
    StockLandedCostLine.objects.create(
        cost=lc, price_unit=Decimal('500.00'),
        split_method=StockLandedCostLine.SPLIT_BY_WEIGHT,
    )
    landed.compute(lc, [ma, mb])
    # 500 por peso: 20/50*500=200 ; 30/50*500=300.
    assert StockValuationAdjustment.objects.get(cost=lc, move=ma).additional_landed_cost == Decimal('200.00')
    assert StockValuationAdjustment.objects.get(cost=lc, move=mb).additional_landed_cost == Decimal('300.00')


def test_landed_cost_validate_raises_avco_cost(db):
    product = _product()
    move = _receipt(product, '10', '100.00')   # AVCO 100, former 1000
    costing = ProductCosting.objects.get(product=product)
    assert costing.standard_price == Decimal('100.0000')
    lc = StockLandedCost.objects.create(name='Flete')
    StockLandedCostLine.objects.create(
        cost=lc, price_unit=Decimal('200.00'),
        split_method=StockLandedCostLine.SPLIT_BY_QUANTITY,
    )
    landed.compute(lc, [move])
    landed.validate(lc)
    assert lc.state == StockLandedCost.STATE_DONE
    # Revaluación: SVL de valor 200 (cantidad 0) ligada al movimiento.
    reval = StockValuationLayer.objects.filter(stock_move=move, quantity=0).first()
    assert reval.value == Decimal('200.00')
    # AVCO sube: (1000 + 200) / 10 = 120.
    costing.refresh_from_db()
    assert costing.standard_price == Decimal('120.0000')
    # La siguiente entrega valúa a 120 (costo real con flete incluido).
    out = valuation.deliver(product, Decimal('1'))
    assert out.unit_cost == Decimal('120.0000')


def test_amount_total_sums_cost_lines(db):
    lc = StockLandedCost.objects.create(name='Multi')
    StockLandedCostLine.objects.create(cost=lc, price_unit=Decimal('120.00'))
    StockLandedCostLine.objects.create(cost=lc, price_unit=Decimal('80.00'))
    assert lc.amount_total() == Decimal('200.00')
