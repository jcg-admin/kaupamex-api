"""Tests — ``stock.lot`` + dimensión de lote en ``stock.quant`` (addon ``stock``).

Cubre la base que ``product_expiry`` extiende: el lote (``StockLot``) con su
cantidad a la mano computada sobre los quants, la dimensión ``lot`` en el quant
(quants por lote coexistiendo con el quant sin lote) y el orden de remoción de
la base (FIFO por ``in_date``, LIFO por ``-in_date``). La estrategia FEFO la
añade el satélite ``product_expiry`` — aquí se verifica solo la base.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from addons.catalogue.models import Product
from addons.stock.models import StockLocation, StockLot, StockQuant

pytestmark = pytest.mark.integration

_slug_seq = [0]


def _product(price='100.00'):
    _slug_seq[0] += 1
    n = _slug_seq[0]
    return Product.objects.create(
        name=f'Lot Prod {n}', slug=f'lot-prod-{n}', sku=f'LOT-{n:04d}',
        price=Decimal(price),
    )


def _internal(name='WH/Stock'):
    return StockLocation.objects.create(name=name, usage=StockLocation.USAGE_INTERNAL)


def test_lot_product_qty_sums_its_quants(db):
    product = _product()
    loc = _internal()
    lot = StockLot.objects.create(name='LOT-A', product=product)
    StockQuant.objects.create(product=product, location=loc, lot=lot,
                              quantity=Decimal('7.00'))
    other = _internal('WH/Stock2')
    StockQuant.objects.create(product=product, location=other, lot=lot,
                              quantity=Decimal('3.00'))
    # product_qty agrega la cantidad de todos los quants del lote.
    assert lot.product_qty == Decimal('10.00')


def test_lot_and_nonlot_quants_coexist_at_same_location(db):
    product = _product()
    loc = _internal()
    lot = StockLot.objects.create(name='LOT-B', product=product)
    # El quant sin lote y el quant con lote son filas distintas (unique incluye lot).
    StockQuant.objects.create(product=product, location=loc, lot=None,
                              quantity=Decimal('2.00'))
    StockQuant.objects.create(product=product, location=loc, lot=lot,
                              quantity=Decimal('5.00'))
    assert StockQuant.objects.filter(product=product, location=loc).count() == 2
    # available_qty agrega ambos (réplica de _get_available_quantity de Odoo).
    assert StockQuant.available_qty(product, loc) == Decimal('7.00')


def test_gather_fifo_orders_oldest_in_date_first(db):
    product = _product()
    loc = _internal()
    l_old = StockLot.objects.create(name='OLD', product=product)
    l_new = StockLot.objects.create(name='NEW', product=product)
    now = timezone.now()
    q_new = StockQuant.objects.create(product=product, location=loc, lot=l_new,
                                      quantity=Decimal('4.00'))
    q_old = StockQuant.objects.create(product=product, location=loc, lot=l_old,
                                      quantity=Decimal('6.00'))
    # Forzar in_date: old anterior a new.
    StockQuant.objects.filter(pk=q_old.pk).update(in_date=now - timedelta(days=2))
    StockQuant.objects.filter(pk=q_new.pk).update(in_date=now - timedelta(days=1))
    fifo = list(StockQuant.gather(product, loc, removal_strategy='fifo'))
    assert [q.pk for q in fifo] == [q_old.pk, q_new.pk]
    lifo = list(StockQuant.gather(product, loc, removal_strategy='lifo'))
    assert [q.pk for q in lifo] == [q_new.pk, q_old.pk]


def test_gather_excludes_zero_quantity_quants(db):
    product = _product()
    loc = _internal()
    lot = StockLot.objects.create(name='Z', product=product)
    StockQuant.objects.create(product=product, location=loc, lot=lot,
                              quantity=Decimal('0.00'))
    # gather solo devuelve quants con cantidad > 0 (réplica de _gather de Odoo).
    assert list(StockQuant.gather(product, loc)) == []


def test_lot_name_unique_per_product(db):
    product = _product()
    StockLot.objects.create(name='DUP', product=product)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StockLot.objects.create(name='DUP', product=product)
    # El mismo nombre en OTRO producto sí es válido.
    other = _product()
    StockLot.objects.create(name='DUP', product=other)
    assert StockLot.objects.filter(name='DUP').count() == 2
