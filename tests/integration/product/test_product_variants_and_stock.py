"""Tests de integración — ``product`` + ``stock`` (ex ``catalogue``/``chartsize``).

``catalogue`` y ``chartsize`` fueron eliminados por completo (modelos, vistas,
serializers, management commands): no queda superficie HTTP ni serializer que
ejercitar todavía en ``addons.product`` — es un puerto model-only de Odoo. Estos
tests cubren, contra MariaDB real, lo que SÍ existe: la generación cartesiana de
combinaciones (``addons.product.services``), la existencia derivada de
``stock.quant`` (no una columna ``stock`` en el producto — el rename más
importante de la migración) y la tarifa de proveedor (``code_for``/
``partner_ref_for``).
"""
from decimal import Decimal

import pytest

from addons.product import services as pa_services
from addons.base.models import ResPartner
from addons.product.models import (
    ProductAttribute,
    ProductAttributeValue,
    ProductProduct,
    ProductSupplierinfo,
    ProductTemplate,
    ProductTemplateAttributeLine,
)
from addons.stock.models import StockLocation, StockQuant
from addons.stock.services import InsufficientStockError, InventoryService
from tests.factories.product_factory import get_stock, make_product

pytestmark = pytest.mark.integration


def _attribute(name, values):
    attr = ProductAttribute.objects.create(name=name)
    objs = [
        ProductAttributeValue.objects.create(attribute=attr, name=v, sequence=i)
        for i, v in enumerate(values)
    ]
    return attr, objs


def _line(product_tmpl, attr, values, sequence=10):
    line = ProductTemplateAttributeLine.objects.create(
        product_tmpl=product_tmpl, attribute=attr, sequence=sequence)
    line.values.set(values)
    return line


# =============================================================================
# Generación cartesiana de variantes (addons.product.services)
# =============================================================================

class TestCartesianCombinations:

    def test_sin_lineas_una_combinacion_vacia(self, db):
        tmpl = ProductTemplate.objects.create(name='Eleke simple')
        assert pa_services.combinations(tmpl) == [()]
        assert pa_services.combination_count(tmpl) == 0

    def test_un_eje_genera_una_combinacion_por_valor(self, db):
        color, valores = _attribute('Color', ['Rojo', 'Azul'])
        tmpl = ProductTemplate.objects.create(name='Eleke')
        _line(tmpl, color, valores)
        combos = pa_services.combinations(tmpl)
        assert len(combos) == 2
        assert pa_services.combination_count(tmpl) == 2

    def test_dos_ejes_multiplican_las_combinaciones(self, db):
        color, colores = _attribute('Color', ['Rojo', 'Azul'])
        talla, tallas = _attribute('Talla', ['S', 'M', 'L'])
        tmpl = ProductTemplate.objects.create(name='Pulsera')
        _line(tmpl, color, colores, sequence=1)
        _line(tmpl, talla, tallas, sequence=2)
        combos = pa_services.combinations(tmpl)
        # 2 colores x 3 tallas = 6 combinaciones.
        assert len(combos) == 6
        assert pa_services.combination_count(tmpl) == 6
        assert all(len(c) == 2 for c in combos)

    def test_atributo_es_reutilizable_entre_fichas(self, db):
        color, valores = _attribute('Color', ['Rojo', 'Azul'])
        tmpl_a = ProductTemplate.objects.create(name='Eleke A')
        tmpl_b = ProductTemplate.objects.create(name='Eleke B')
        _line(tmpl_a, color, valores)
        _line(tmpl_b, color, [valores[0]])
        assert color.template_lines.count() == 2
        assert valores[0].template_lines.count() == 2


# =============================================================================
# Existencia de producto — DERIVADA de stock.quant, NO una columna
# =============================================================================
# El rename más importante de la migración: `Product.stock` (entero, columna
# directa) desaparece. La existencia se deriva de `stock.quant` a través de
# `InventoryService.available_quantity` / `StockQuant.available_qty`.

class TestExistenciaDerivadaDeStockQuant:

    def test_variante_sin_quants_no_tiene_disponibilidad(self, db):
        variante = make_product(name='Eleke', price=Decimal('100.00'))
        assert get_stock(variante) == Decimal('0.00')

    def test_dar_stock_a_un_producto_crea_un_quant(self, db):
        """Cómo se le da existencia a un producto en un test: ``set_stock``
        (o ``make_product(..., stock=N)``) crea un ``StockQuant`` en la
        ubicación interna por defecto — no se asigna un entero."""
        variante = make_product(name='Eleke', stock=7)
        assert get_stock(variante) == Decimal('7.00')

    def test_reserva_descuenta_de_la_disponibilidad(self, db):
        variante = make_product(name='Eleke')
        almacen = StockLocation.objects.create(
            name='WH/Stock2', usage=StockLocation.USAGE_INTERNAL)
        StockQuant.objects.create(
            product=variante, location=almacen,
            quantity=Decimal('7.00'), reserved_quantity=Decimal('2.00'))
        assert get_stock(variante) == Decimal('5.00')

    def test_decrement_agota_y_levanta_si_no_alcanza(self, db):
        variante = make_product(name='Eleke', stock=3)
        InventoryService.decrement(
            [{'product': variante, 'quantity': Decimal('2.00')}])
        assert get_stock(variante) == Decimal('1.00')
        with pytest.raises(InsufficientStockError):
            InventoryService.decrement(
                [{'product': variante, 'quantity': Decimal('5.00')}])

    def test_ubicacion_proveedor_no_bloquea_la_reserva(self, db):
        """Las ubicaciones no-internas (proveedor, cliente...) tienen
        disponibilidad "infinita" a efectos de reserva (should_bypass_reservation)."""
        variante = make_product(name='Eleke')
        proveedor = StockLocation.objects.create(
            name='Proveedores', usage=StockLocation.USAGE_SUPPLIER)
        assert StockQuant.available_qty(variante, proveedor) == Decimal('999999999.00')


# =============================================================================
# Tarifa de proveedor — code_for / partner_ref_for (asimetría plantilla/variante)
# =============================================================================

class TestSupplierinfoCodeFor:

    def test_sin_tarifa_del_proveedor_devuelve_la_referencia_interna(self, db):
        tmpl = ProductTemplate.objects.create(name='Eleke')
        variante = ProductProduct.objects.create(
            product_tmpl=tmpl, default_code='ELK-001')
        comprador = ResPartner.objects.create(name='Comprador de prueba')
        assert variante.code_for(comprador) == 'ELK-001'

    def test_tarifa_de_variante_pisa_a_la_de_plantilla(self, db):
        """La fila específica de la variante gana sobre la de la plantilla
        (docstring de ProductProduct.code_for): el bucle no corta en la
        primera coincidencia, sigue hasta encontrar la de la variante."""
        tmpl = ProductTemplate.objects.create(name='Eleke')
        variante = ProductProduct.objects.create(
            product_tmpl=tmpl, default_code='ELK-001')
        proveedor = ResPartner.objects.create(name='Proveedor de prueba')
        ProductSupplierinfo.objects.create(
            partner=proveedor, product_tmpl=tmpl, product_code='PROV-TMPL')
        ProductSupplierinfo.objects.create(
            partner=proveedor, product_tmpl=tmpl, product=variante,
            product_code='PROV-VARIANTE')
        assert variante.code_for(proveedor) == 'PROV-VARIANTE'
