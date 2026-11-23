"""``stock.move.line`` escribe y borra con la firma de recordset de la fuente.

≙ ``write(self, vals)`` y ``unlink(self)``
(``odoo19c: addons/stock/models/stock_move_line.py:421-546``, ``:557-575``).
Antes eran métodos de clase que recibían una lista, y ``line.write(vals)``
tomaba el diccionario por la lista de líneas.
"""

from decimal import Decimal

import pytest

from addons.base.models import ResCompany
from addons.product.models import ProductProduct, ProductTemplate
from addons.stock.models import (
    StockLocation,
    StockMoveLine,
    StockPicking,
    StockPickingType,
)
from addons.uom.models.uom_uom import Uom


@pytest.fixture
def line(db):
    company = ResCompany.objects.create(
        name='Kaupamex', code='kaupamex_test_mlcrud')
    source = StockLocation.objects.create(
        name='Stock MLCRUD', usage='internal')
    destination = StockLocation.objects.create(
        name='Customers MLCRUD', usage='customer')
    uom = Uom.objects.create(name='Unidad MLCRUD')
    template = ProductTemplate.objects.create(
        name='Camisa MLCRUD', list_price=Decimal('100.00'),
        is_storable=True, uom_id=uom)
    variant = ProductProduct.objects.create(
        product_tmpl_id=template, default_code='CAM-MLCRUD')
    picking_type = StockPickingType.objects.create(
        name='Entrega MLCRUD', code='outgoing', sequence_code='OUTMLCRUD',
        company=company)
    picking = StockPicking.objects.create(
        name='OUT/MLCRUD', company=company, location=source,
        location_dest=destination, picking_type=picking_type,
        state=StockPicking.STATE_ASSIGNED)
    return StockMoveLine.objects.create(
        picking=picking, product=variant, location=source,
        location_dest=destination, company=company,
        quantity=Decimal('5'), state='draft')


def test_write_takes_the_values_on_the_recordset(line):
    assert line.write({'quantity': Decimal('3')}) is True
    assert StockMoveLine.objects.get(pk=line.pk).quantity == Decimal('3')


def test_unlink_deletes_the_recordset(line):
    pk = line.pk
    line.unlink()
    assert not StockMoveLine.objects.filter(pk=pk).exists()
