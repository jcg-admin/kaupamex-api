"""``stock.picking`` y ``stock.scrap`` sobre el recordset de la fuente.

≙ ``StockPicking.write``/``unlink`` y ``_compute_scheduled_date``/
``_set_scheduled_date`` (``odoo19c: addons/stock/models/stock_picking.py:
864-873``, ``:925-931``, ``:1139-1173``) y ``StockScrap._unlink_except_done``
(``addons/stock/models/stock_scrap.py:120-123``).
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.base.models import ResCompany
from addons.product.models import ProductProduct, ProductTemplate
from addons.stock.models import (
    StockLocation,
    StockMove,
    StockPicking,
    StockPickingType,
    StockScrap,
)
from addons.uom.models.uom_uom import Uom
from exceptions import UserError


@pytest.fixture
def env_data(db):
    company = ResCompany.objects.create(
        name='Kaupamex', code='kaupamex_test_pkcrud')
    source = StockLocation.objects.create(
        name='Stock PKCRUD', usage='internal')
    destination = StockLocation.objects.create(
        name='Customers PKCRUD', usage='customer')
    loss = StockLocation.objects.create(
        name='Scrap PKCRUD', usage='inventory')
    uom = Uom.objects.create(name='Unidad PKCRUD')
    template = ProductTemplate.objects.create(
        name='Camisa PKCRUD', list_price=Decimal('100.00'),
        is_storable=True, uom_id=uom)
    variant = ProductProduct.objects.create(
        product_tmpl_id=template, default_code='CAM-PKCRUD')
    picking_type = StockPickingType.objects.create(
        name='Entrega PKCRUD', code='outgoing', sequence_code='OUTPKCRUD',
        company=company)
    return {
        'company': company, 'source': source, 'destination': destination,
        'loss': loss,
        'uom': uom, 'variant': variant, 'picking_type': picking_type,
    }


def _picking(data, **extra):
    return StockPicking.objects.create(
        picking_type=data['picking_type'], company=data['company'],
        location=data['source'], location_dest=data['destination'], **extra)


def _move(data, picking, **extra):
    values = dict(
        picking=picking, product=data['variant'], location=data['source'],
        location_dest=data['destination'], company=data['company'],
        product_uom=data['uom'], product_uom_qty=Decimal('1'))
    values.update(extra)
    return StockMove.objects.create(**values)


def test_unlink_deletes_every_picking_and_its_draft_moves(env_data):
    first, second = _picking(env_data), _picking(env_data)
    moves = [_move(env_data, first), _move(env_data, second)]
    pickings = first | second
    ids = pickings.ids
    pickings.unlink()
    assert not StockPicking.objects.filter(pk__in=ids).exists()
    assert not StockMove.objects.filter(
        pk__in=[move.pk for move in moves]).exists()


def test_scheduled_date_follows_the_earliest_pending_move(env_data):
    picking = _picking(env_data, move_type='direct')
    early = timezone.now() + timedelta(days=1)
    late = early + timedelta(days=2)
    _move(env_data, picking, date=late)
    _move(env_data, picking, date=early)
    _move(env_data, picking, date=early - timedelta(days=5), state='done')
    picking._compute_scheduled_date()
    assert picking.scheduled_date == early


def test_scheduled_date_follows_the_latest_move_when_shipping_at_once(
        env_data):
    picking = _picking(env_data, move_type='one')
    early = timezone.now() + timedelta(days=1)
    late = early + timedelta(days=2)
    _move(env_data, picking, date=late)
    _move(env_data, picking, date=early)
    picking._compute_scheduled_date()
    assert picking.scheduled_date == late


def test_writing_scheduled_date_moves_the_pending_moves(env_data):
    picking = _picking(env_data, state='assigned')
    move = _move(env_data, picking)
    when = timezone.now() + timedelta(days=3)
    picking.write({'scheduled_date': when})
    assert StockMove.objects.get(pk=move.pk).date == when


def test_a_done_scrap_cannot_be_unlinked(env_data):
    scrap = StockScrap.objects.create(
        product=env_data['variant'], company=env_data['company'],
        location=env_data['source'], scrap_location=env_data['loss'],
        scrap_qty=Decimal('1'), state='done')
    with pytest.raises(UserError):
        scrap.unlink()
    assert StockScrap.objects.filter(pk=scrap.pk).exists()


def test_a_draft_scrap_is_unlinked(env_data):
    scrap = StockScrap.objects.create(
        product=env_data['variant'], company=env_data['company'],
        location=env_data['source'], scrap_location=env_data['loss'],
        scrap_qty=Decimal('1'))
    pk = scrap.pk
    scrap.unlink()
    assert not StockScrap.objects.filter(pk=pk).exists()
