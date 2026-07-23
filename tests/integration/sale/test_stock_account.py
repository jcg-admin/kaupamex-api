"""Tests — addon ``stock_account`` (valoración de inventario).

Cubre el rastreo del **costo unitario real de entrega**: método estándar,
promedio móvil (AVCO) y FIFO. Cada entrada/salida crea una
``StockValuationLayer``; la salida graba el ``unit_cost`` con que se valuó, que
es el costo real de esa entrega.
"""
from decimal import Decimal

import pytest

from addons.catalogue.models import Product
from addons.stock.models import StockLocation, StockMove
from addons.stock_account import services as valuation
from addons.stock_account.models import ProductCosting, StockValuationLayer

pytestmark = pytest.mark.integration

_slug_seq = [0]


def _product(price='100.00'):
    _slug_seq[0] += 1
    n = _slug_seq[0]
    return Product.objects.create(
        name=f'Val {n}', slug=f'val-prod-{n}', sku=f'VAL-{n:04d}',
        price=Decimal(price),
    )


def _internal(name='WH/Stock'):
    return StockLocation.objects.create(name=name, usage=StockLocation.USAGE_INTERNAL)


def _supplier():
    return StockLocation.objects.create(name='Vendors', usage=StockLocation.USAGE_SUPPLIER)


def _customer():
    return StockLocation.objects.create(name='Customers', usage=StockLocation.USAGE_CUSTOMER)


def test_standard_costing_out_unit_cost(db):
    product = _product()
    ProductCosting.for_product(product, cost_method=ProductCosting.COST_STANDARD)
    valuation.receive(product, Decimal('10'), Decimal('50.00'))
    out = valuation.deliver(product, Decimal('3'))
    # Estándar: costo unitario fijo = el de la primera entrada.
    assert out.unit_cost == Decimal('50.0000')
    assert out.quantity == Decimal('-3.00')
    assert out.value == Decimal('-150.00')


def test_average_costing_recomputes_running_cost(db):
    product = _product()
    ProductCosting.for_product(product, cost_method=ProductCosting.COST_AVERAGE)
    valuation.receive(product, Decimal('10'), Decimal('100.00'))  # valor 1000
    valuation.receive(product, Decimal('10'), Decimal('200.00'))  # valor 2000
    costing = ProductCosting.objects.get(product=product)
    # AVCO: (1000 + 2000) / 20 = 150.00.
    assert costing.standard_price == Decimal('150.0000')
    out = valuation.deliver(product, Decimal('5'))
    assert out.unit_cost == Decimal('150.0000')
    assert out.value == Decimal('-750.00')


def test_fifo_costing_consumes_oldest_layers(db):
    product = _product()
    ProductCosting.for_product(product, cost_method=ProductCosting.COST_FIFO)
    valuation.receive(product, Decimal('10'), Decimal('100.00'))  # capa 1 @100
    valuation.receive(product, Decimal('10'), Decimal('200.00'))  # capa 2 @200
    # Entregar 15: consume 10@100 + 5@200 = 1000 + 1000 = 2000; unit=133.3333.
    out = valuation.deliver(product, Decimal('15'))
    assert out.value == Decimal('-2000.00')
    assert out.unit_cost == Decimal('133.3333')
    # Primera capa agotada, segunda con saldo 5 @200 = 1000.
    layers = StockValuationLayer.objects.filter(product=product, quantity__gt=0).order_by('id')
    assert layers[0].remaining_qty == Decimal('0.00')
    assert layers[1].remaining_qty == Decimal('5.00')
    assert layers[1].remaining_value == Decimal('1000.00')


def test_fifo_negative_stock_uses_last_cost(db):
    product = _product()
    ProductCosting.for_product(product, cost_method=ProductCosting.COST_FIFO)
    valuation.receive(product, Decimal('5'), Decimal('80.00'))  # solo 5 disponibles
    # Entregar 8: 5@80 = 400, faltan 3 valuadas al último costo 80 = 240 → 640.
    out = valuation.deliver(product, Decimal('8'))
    assert out.value == Decimal('-640.00')
    assert out.unit_cost == Decimal('80.0000')


def test_value_move_receipt_then_delivery(db):
    product = _product()
    ProductCosting.for_product(product, cost_method=ProductCosting.COST_AVERAGE)
    src = _supplier()
    stock = _internal('WH/Stock')
    cust = _customer()
    # Movimiento de entrada (proveedor → interno) valuado a 120.
    in_move = StockMove.objects.create(
        product=product, product_uom_qty=Decimal('4'), quantity=Decimal('4'),
        location=src, location_dest=stock,
    )
    in_layer = valuation.value_move(in_move, unit_cost=Decimal('120.00'))
    assert in_layer.quantity == Decimal('4.00')
    assert in_layer.value == Decimal('480.00')
    assert in_layer.stock_move_id == in_move.id
    # Movimiento de salida (interno → cliente): usa el AVCO (=120).
    out_move = StockMove.objects.create(
        product=product, product_uom_qty=Decimal('2'), quantity=Decimal('2'),
        location=stock, location_dest=cust,
    )
    out_layer = valuation.value_move(out_move)
    assert out_layer.unit_cost == Decimal('120.0000')
    assert out_layer.value == Decimal('-240.00')
    assert out_layer.stock_move_id == out_move.id


def test_value_move_internal_transfer_no_layer(db):
    product = _product()
    a = _internal('WH/A')
    b = _internal('WH/B')
    move = StockMove.objects.create(
        product=product, product_uom_qty=Decimal('3'), quantity=Decimal('3'),
        location=a, location_dest=b,
    )
    # Transferencia interna → interna: sin cambio de valor.
    assert valuation.value_move(move) is None
    assert StockValuationLayer.objects.filter(product=product).count() == 0
