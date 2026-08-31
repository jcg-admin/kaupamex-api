"""``PurchaseOrderLine._get_outgoing_incoming_moves`` — el reparto que decide
lo recibido.

Fiel a ``odoo19c: addons/purchase_stock/models/purchase_order_line.py:401-413``
(``odoo-tools``, LGPL-3). El método separa los movimientos de una línea de
compra en los que **salen** hacia el proveedor —una devolución— y los que
**entran**. De ese reparto sale la cantidad recibida de la línea.

``to_refund`` es la bisagra, y es lo que estos casos discriminan: una
devolución **con** la bandera resta de lo recibido; una **sin** ella devuelve
mercancía sin tocar la orden. Un reparto que ignorara la bandera daría el mismo
resultado para las dos, que es exactamente el defecto que la fuente evita.
"""
from decimal import Decimal

import pytest

from addons.base.models import ResCompany, ResUsers
from addons.product.models import ProductProduct, ProductTemplate
from addons.purchase.models import PurchaseOrder, PurchaseOrderLine
from addons.stock.models import StockLocation, StockMove

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def company(db):
    return ResCompany.objects.create(name='Kaupamex', code='kaupamex_pol')


@pytest.fixture
def supplier_location(db):
    return StockLocation.objects.create(name='Vendors', usage='supplier')


@pytest.fixture
def stock_location(db):
    return StockLocation.objects.create(name='Stock', usage='internal')


@pytest.fixture
def scrap_location(db):
    return StockLocation.objects.create(name='Inventory adjustment',
                                        usage='inventory')


@pytest.fixture
def variant(db):
    tmpl = ProductTemplate.objects.create(name='Eleke', list_price=Decimal('10.00'))
    return ProductProduct.objects.create(product_tmpl=tmpl)


@pytest.fixture
def line(db, variant):
    order = PurchaseOrder.objects.create(
        partner_id=ResUsers.objects.create_user(
            login='proveedor@kaupamex.mx', password='x'))
    return PurchaseOrderLine.objects.create(
        order_id=order, product_id=variant, price_unit=Decimal('10.00'))


def _move(line, variant, company, origin, destination, **extra):
    """Un movimiento enganchado a la línea, con lo mínimo para insertarlo."""
    values = dict(product=variant, location=origin, location_dest=destination,
                  company=company, product_uom=variant.product_tmpl.uom,
                  product_uom_qty=Decimal('1'), purchase_line=line)
    values.update(extra)
    return StockMove.objects.create(**values)


def test_a_plain_reception_is_incoming(
        line, variant, company, supplier_location, stock_location):
    """La recepción normal —del proveedor al almacén— entra."""
    reception = _move(line, variant, company, supplier_location, stock_location)
    outgoing, incoming = line._get_outgoing_incoming_moves()
    assert incoming == [reception]
    assert outgoing == []


def test_a_return_with_the_flag_is_outgoing(
        line, variant, company, supplier_location, stock_location):
    """La devolución al proveedor **con** ``to_refund`` sale, y por tanto
    resta de lo recibido."""
    reception = _move(line, variant, company, supplier_location, stock_location)
    devolution = _move(line, variant, company, stock_location, supplier_location,
                       to_refund=True, origin_returned_move=reception)
    outgoing, incoming = line._get_outgoing_incoming_moves()
    assert outgoing == [devolution]
    assert incoming == [reception]


def test_a_return_without_the_flag_is_neither(
        line, variant, company, supplier_location, stock_location):
    """**El caso que discrimina.** La misma devolución **sin** ``to_refund`` no
    entra ni sale: devuelve mercancía sin tocar la cantidad recibida.

    Un reparto que ignorara la bandera la clasificaría igual que la del caso
    anterior, y la orden diría haber recibido de menos.
    """
    reception = _move(line, variant, company, supplier_location, stock_location)
    _move(line, variant, company, stock_location, supplier_location,
          to_refund=False, origin_returned_move=reception)
    outgoing, incoming = line._get_outgoing_incoming_moves()
    assert outgoing == []
    assert incoming == [reception]


def test_an_incoming_return_without_the_flag_is_dropped(
        line, variant, company, supplier_location, stock_location):
    """La otra rama: un movimiento que **entra** y es devolución de otro sin
    ``to_refund`` tampoco cuenta (``if not origin or to_refund``)."""
    original = _move(line, variant, company, supplier_location, stock_location)
    _move(line, variant, company, supplier_location, stock_location,
          to_refund=False, origin_returned_move=original)
    outgoing, incoming = line._get_outgoing_incoming_moves()
    assert incoming == [original]
    assert outgoing == []


def test_a_cancelled_move_counts_for_neither(
        line, variant, company, supplier_location, stock_location):
    _move(line, variant, company, supplier_location, stock_location,
          state=StockMove.STATE_CANCEL)
    assert line._get_outgoing_incoming_moves() == ([], [])


def test_a_move_towards_inventory_counts_for_neither(
        line, variant, company, supplier_location, scrap_location):
    """``location_dest_usage != 'inventory'`` — un ajuste no es una recepción."""
    _move(line, variant, company, supplier_location, scrap_location)
    assert line._get_outgoing_incoming_moves() == ([], [])


def test_a_move_of_another_product_counts_for_neither(
        line, variant, company, supplier_location, stock_location):
    """El filtro por producto no es redundante: con un kit los movimientos
    entregados no coinciden con el producto de la línea."""
    other_tmpl = ProductTemplate.objects.create(name='Otro',
                                                list_price=Decimal('1.00'))
    other = ProductProduct.objects.create(product_tmpl=other_tmpl)
    _move(line, other, company, supplier_location, stock_location)
    assert line._get_outgoing_incoming_moves() == ([], [])
