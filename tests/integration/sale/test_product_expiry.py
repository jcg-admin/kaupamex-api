"""Tests — addon ``product_expiry`` (caducidad + FEFO).

Cubre la extensión de caducidad sobre la base ``stock``: el cálculo de las
fechas del lote desde la config del producto (``compute_lot_dates``), la alerta
de caducidad alcanzada (``product_expiry_alert``), la estrategia de remoción
FEFO (``fefo_gather`` ordena por ``removal_date``) y el barrido de alertas
(``alert_date_exceeded`` marca los lotes vencidos con existencia interna).
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.product_expiry import services as exp
from addons.product_expiry.models import ProductExpiryConfig, StockLotExpiry
from addons.stock.models import StockLocation, StockLot, StockQuant
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.integration

_slug_seq = [0]


def _product(price='100.00'):
    _slug_seq[0] += 1
    n = _slug_seq[0]
    return make_product(
        name=f'Exp Prod {n}', default_code=f'EXP-{n:04d}',
        price=Decimal(price),
    )


def _internal(name='WH/Stock'):
    return StockLocation.objects.create(name=name, usage=StockLocation.USAGE_INTERNAL)


def _tracked(product, expiration=30, use=20, removal=25, alert=15):
    return ProductExpiryConfig.objects.create(
        product=product, use_expiration_date=True,
        expiration_time=expiration, use_time=use, removal_time=removal, alert_time=alert,
    )


def test_compute_lot_dates_from_product_config(db):
    product = _product()
    _tracked(product, expiration=30, use=20, removal=25, alert=15)
    lot = StockLot.objects.create(name='L1', product=product)
    expiry = exp.compute_lot_dates(lot)
    # Caducidad = ahora + 30 días (tolerancia de 1 min por el now()).
    delta = expiry.expiration_date - timezone.now()
    assert timedelta(days=29, hours=23) < delta <= timedelta(days=30)
    # removal = caducidad − 25 días; use = −20; alert = −15.
    assert expiry.removal_date == expiry.expiration_date - timedelta(days=25)
    assert expiry.use_date == expiry.expiration_date - timedelta(days=20)
    assert expiry.alert_date == expiry.expiration_date - timedelta(days=15)


def test_compute_lot_dates_no_config_clears_dates(db):
    product = _product()  # sin ProductExpiryConfig.
    lot = StockLot.objects.create(name='L2', product=product)
    expiry = exp.compute_lot_dates(lot)
    assert expiry.expiration_date is None
    assert expiry.removal_date is None


def test_product_expiry_alert_true_when_expired(db):
    product = _product()
    lot = StockLot.objects.create(name='L3', product=product)
    past = StockLotExpiry.objects.create(
        lot=lot, expiration_date=timezone.now() - timedelta(days=1))
    assert past.product_expiry_alert is True
    lot2 = StockLot.objects.create(name='L4', product=product)
    future = StockLotExpiry.objects.create(
        lot=lot2, expiration_date=timezone.now() + timedelta(days=1))
    assert future.product_expiry_alert is False


def test_fefo_gather_orders_earliest_removal_date_first(db):
    product = _product()
    loc = _internal()
    l_late = StockLot.objects.create(name='LATE', product=product)
    l_soon = StockLot.objects.create(name='SOON', product=product)
    now = timezone.now()
    StockLotExpiry.objects.create(lot=l_late, removal_date=now + timedelta(days=60))
    StockLotExpiry.objects.create(lot=l_soon, removal_date=now + timedelta(days=5))
    q_late = StockQuant.objects.create(product=product, location=loc, lot=l_late,
                                       quantity=Decimal('3.00'))
    q_soon = StockQuant.objects.create(product=product, location=loc, lot=l_soon,
                                       quantity=Decimal('4.00'))
    order = list(exp.fefo_gather(product, loc))
    # El lote que se retira antes (SOON) sale primero.
    assert [q.pk for q in order] == [q_soon.pk, q_late.pk]


def test_alert_date_exceeded_marks_reminded_with_internal_stock(db):
    product = _product()
    loc = _internal()
    lot = StockLot.objects.create(name='ALERT', product=product)
    expiry = StockLotExpiry.objects.create(
        lot=lot, alert_date=timezone.now() - timedelta(days=1))
    StockQuant.objects.create(product=product, location=loc, lot=lot,
                              quantity=Decimal('2.00'))
    marked = exp.alert_date_exceeded()
    expiry.refresh_from_db()
    assert expiry.product_expiry_reminded is True
    assert lot.expiry in marked


def test_alert_date_exceeded_skips_lots_without_internal_stock(db):
    product = _product()
    lot = StockLot.objects.create(name='NOSTOCK', product=product)
    expiry = StockLotExpiry.objects.create(
        lot=lot, alert_date=timezone.now() - timedelta(days=1))
    # Sin quant a la mano en ubicación interna → no se notifica.
    exp.alert_date_exceeded()
    expiry.refresh_from_db()
    assert expiry.product_expiry_reminded is False
