"""Contrato de ``InventoryService`` — disponibilidad derivada de ``stock.quant``.

Fiel a ``odoo19c: addons/stock/models/stock_quant.py`` (``odoo-tools@622ddc2a``):

- ``:87-90,119-122`` — ``available_quantity`` es un **computado**
  ``quantity - reserved_quantity``, con ``@api.depends('quantity',
  'reserved_quantity')``. No es una columna escrita a mano.
- ``:635`` — la agregación por producto es
  ``SUM(quantity - reserved_quantity)``, es decir la suma sobre **todos** los
  quants (ubicaciones) del producto.

Y a ``odoo19c: addons/sale/models/sale_order_line.py:83-88`` — la línea de
venta apunta a ``product.product``, la **variante**. Por eso el servicio se
indexa por variante y no acepta un eje ``variant`` separado: la variante *es*
el producto. Ver :ref:`analisis-destino-por-addon-del-fk-producto` §2.
"""
from decimal import Decimal

import pytest

from addons.base.models import ResCompany
from addons.product.models import ProductProduct, ProductTemplate
from addons.stock.models import StockLocation, StockQuant
from addons.stock.services import InsufficientStockError, InventoryService

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def location(db):
    return StockLocation.objects.create(name='WH/Stock', usage='internal')


@pytest.fixture
def variant(db):
    tmpl = ProductTemplate.objects.create(name='Camisa', list_price=Decimal('100.00'))
    return ProductProduct.objects.create(product_tmpl=tmpl, default_code='CAM-M')


def _quant(variant, location, qty, reserved=Decimal('0.00')):
    return StockQuant.objects.create(
        product=variant, location=location,
        quantity=Decimal(qty), reserved_quantity=Decimal(reserved),
    )


class TestAvailableQuantity:
    def test_sin_quants_es_cero(self, variant):
        assert InventoryService.available_quantity(variant) == Decimal('0.00')

    def test_descuenta_lo_reservado(self, variant, location):
        # odoo19c stock_quant.py:122 — quantity - reserved_quantity.
        _quant(variant, location, '10.00', '4.00')
        assert InventoryService.available_quantity(variant) == Decimal('6.00')

    def test_suma_todas_las_ubicaciones(self, variant, location):
        # odoo19c stock_quant.py:635 — SUM(quantity - reserved_quantity).
        otra = StockLocation.objects.create(name='WH/Shelf2', usage='internal')
        _quant(variant, location, '10.00', '4.00')
        _quant(variant, otra, '5.00', '1.00')
        assert InventoryService.available_quantity(variant) == Decimal('10.00')


class TestCheckAvailability:
    def test_todo_disponible_devuelve_vacio(self, variant, location):
        _quant(variant, location, '10.00')
        items = [{'product': variant, 'quantity': Decimal('3.00')}]
        assert InventoryService.check_availability(items) == []

    def test_reporta_el_faltante(self, variant, location):
        _quant(variant, location, '2.00')
        items = [{'product': variant, 'quantity': Decimal('5.00')}]
        faltantes = InventoryService.check_availability(items)
        assert len(faltantes) == 1
        assert faltantes[0]['product'] == variant
        assert faltantes[0]['requested'] == Decimal('5.00')
        assert faltantes[0]['available'] == Decimal('2.00')

    def test_agrega_cantidades_del_mismo_producto(self, variant, location):
        # Dos líneas del mismo SKU compiten por el mismo stock.
        _quant(variant, location, '5.00')
        items = [{'product': variant, 'quantity': Decimal('3.00')},
                 {'product': variant, 'quantity': Decimal('3.00')}]
        faltantes = InventoryService.check_availability(items)
        assert len(faltantes) == 1
        assert faltantes[0]['requested'] == Decimal('6.00')


class TestDecrement:
    def test_descuenta_del_quant(self, variant, location):
        q = _quant(variant, location, '10.00')
        InventoryService.decrement([{'product': variant, 'quantity': Decimal('4.00')}])
        q.refresh_from_db()
        assert q.quantity == Decimal('6.00')

    def test_consume_varias_ubicaciones_en_orden(self, variant, location):
        otra = StockLocation.objects.create(name='WH/Shelf2', usage='internal')
        q1 = _quant(variant, location, '3.00')
        q2 = _quant(variant, otra, '5.00')
        InventoryService.decrement([{'product': variant, 'quantity': Decimal('6.00')}])
        q1.refresh_from_db(); q2.refresh_from_db()
        assert q1.quantity == Decimal('0.00')
        assert q2.quantity == Decimal('2.00')

    def test_sin_stock_suficiente_levanta(self, variant, location):
        _quant(variant, location, '1.00')
        with pytest.raises(InsufficientStockError):
            InventoryService.decrement(
                [{'product': variant, 'quantity': Decimal('5.00')}])


class TestRestore:
    def test_devuelve_al_quant_existente(self, variant, location):
        q = _quant(variant, location, '2.00')
        InventoryService.restore([{'product': variant, 'quantity': Decimal('3.00')}])
        q.refresh_from_db()
        assert q.quantity == Decimal('5.00')

    def test_crea_el_quant_si_no_existe(self, variant):
        InventoryService.restore([{'product': variant, 'quantity': Decimal('3.00')}])
        assert InventoryService.available_quantity(variant) == Decimal('3.00')

    def test_acepta_referencia_y_autor_sin_alterar_el_saldo(self, variant, location, user):
        # ``reference``/``created_by`` son trazabilidad del llamador
        # (cancelación de orden); no cambian la aritmética.
        _quant(variant, location, '1.00')
        InventoryService.restore(
            [{'product': variant, 'quantity': Decimal('2.00')}],
            reference='S-0001', created_by=user,
        )
        assert InventoryService.available_quantity(variant) == Decimal('3.00')
