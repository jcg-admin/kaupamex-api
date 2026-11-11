"""``stock.quant``: producto, ubicación y lote con ``ondelete='restrict'``.

≙ ``odoo19c: addons/stock/models/stock_quant.py:44-47, 56-59, 63-66``:
borrar el padre de unas existencias falla y las existencias se conservan.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
stock-quant-restrict-ondelete.md``.
"""
from decimal import Decimal

import pytest
from django.db.models import ProtectedError

from addons.product.models import ProductProduct, ProductTemplate
from addons.stock.models import StockLocation, StockLot, StockQuant

pytestmark = pytest.mark.django_db


@pytest.fixture
def location():
    return StockLocation.objects.create(name='WH/Stock', usage='internal')


@pytest.fixture
def variant():
    template = ProductTemplate.objects.create(
        name='Tornillo', list_price=Decimal('1.00'))
    return ProductProduct.objects.create(product_tmpl=template)


def _refuses_and_keeps(record, quant):
    with pytest.raises(ProtectedError):
        type(record).objects.filter(pk=record.pk).delete()
    assert StockQuant.objects.filter(pk=quant.pk).exists()


@pytest.mark.parametrize('parent', ['variant', 'location'])
def test_deleting_the_parent_of_a_quant_is_refused(variant, location,
                                                   parent):
    """Sin lote: la única fila que protege al padre es el quant (un lote
    también apunta al producto y ocultaría la política del quant)."""
    quant = StockQuant.objects.create(product=variant, location=location,
                                      quantity=Decimal('3.00'))
    _refuses_and_keeps({'variant': variant, 'location': location}[parent],
                       quant)


def test_deleting_the_lot_of_a_quant_is_refused(variant, location):
    lot = StockLot.objects.create(name='LOT-R', product=variant)
    quant = StockQuant.objects.create(product=variant, location=location,
                                      lot=lot, quantity=Decimal('3.00'))
    _refuses_and_keeps(lot, quant)


def test_a_location_without_quants_can_be_deleted():
    empty = StockLocation.objects.create(name='WH/Empty', usage='internal')
    StockLocation.objects.filter(pk=empty.pk).delete()
    assert not StockLocation.objects.filter(pk=empty.pk).exists()
