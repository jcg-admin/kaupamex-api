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

from addons.stock.models import (
    ProductRemoval, StockLocation, StockLot, StockQuant,
)
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.integration

_slug_seq = [0]


def _product(price='100.00'):
    _slug_seq[0] += 1
    n = _slug_seq[0]
    return make_product(
        name=f'Lot Prod {n}', default_code=f'LOT-{n:04d}',
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


def test_gather_orders_oldest_in_date_first(db):
    """La estrategia por defecto es FIFO: lo más antiguo se retira primero.

    ``_gather`` **no** recibe la estrategia: la deriva de la categoría del
    producto y, si no, subiendo por la cadena de ubicaciones
    (``_get_removal_strategy``). Este test la deja en el default.
    """
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

    assert StockQuant._get_removal_strategy(product, loc) == 'fifo'
    fifo = list(StockQuant._gather(product, loc))
    assert [q.pk for q in fifo] == [q_old.pk, q_new.pk]


def test_gather_lifo_when_the_location_declares_it(db):
    """LIFO se declara en la ubicación, no se pasa por argumento.

    Es el camino que la referencia recorre en ``_get_removal_strategy``
    (``odoo19c: stock_quant.py:618-628``): categoría del producto primero, y si
    no declara nada, se sube por ``location_id`` hasta encontrar una.
    """
    product = _product()
    loc = _internal()
    loc.removal_strategy = ProductRemoval.objects.create(
        name='LIFO', method='lifo')
    loc.save(update_fields=['removal_strategy', 'updated_at'])

    l_old = StockLot.objects.create(name='OLD2', product=product)
    l_new = StockLot.objects.create(name='NEW2', product=product)
    now = timezone.now()
    q_new = StockQuant.objects.create(product=product, location=loc, lot=l_new,
                                      quantity=Decimal('4.00'))
    q_old = StockQuant.objects.create(product=product, location=loc, lot=l_old,
                                      quantity=Decimal('6.00'))
    StockQuant.objects.filter(pk=q_old.pk).update(in_date=now - timedelta(days=2))
    StockQuant.objects.filter(pk=q_new.pk).update(in_date=now - timedelta(days=1))

    assert StockQuant._get_removal_strategy(product, loc) == 'lifo'
    lifo = list(StockQuant._gather(product, loc))
    assert [q.pk for q in lifo] == [q_new.pk, q_old.pk]


def test_gather_incluye_los_quants_en_cero(db):
    """``_gather`` NO filtra por cantidad — corregido 2026-08-14.

    Hasta hoy este test afirmaba lo contrario (``gather`` sólo devolvía
    ``quantity > 0``), y estaba comprobando una invención nuestra: el
    ``_get_gather_domain`` de la referencia (``odoo19c: :750-769``) filtra por
    producto, lote, paquete, propietario y ubicación — **nunca** por cantidad.

    El descarte del quant vacío ocurre después, al repartir la reserva
    (``_get_reserve_quantity``: ``if max_quantity_on_quant <= 0: continue``),
    y esa distinción importa: un quant en cero sigue existiendo y sigue
    contando para ``_merge_quants`` y para el ajuste de inventario.
    """
    product = _product()
    loc = _internal()
    lot = StockLot.objects.create(name='Z', product=product)
    quant = StockQuant.objects.create(product=product, location=loc, lot=lot,
                                      quantity=Decimal('0.00'))
    assert [q.pk for q in StockQuant._gather(product, loc)] == [quant.pk]
    # Y no aporta nada que reservar, que es donde sí se descarta.
    assert StockQuant._get_reserve_quantity(
        product, loc, Decimal('1.00')) == []


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
