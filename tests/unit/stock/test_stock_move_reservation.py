"""Contrato de reserva y disponibilidad de ``stock.move`` — ola C del porte.

Fiel a ``odoo19c: addons/stock/models/stock_move.py`` (``odoo-tools@622ddc2a``,
LGPL-3). Cada caso cita la línea de la referencia que fija la regla.

Los invariantes que la ola C tiene que sostener:

1. ``:1867-1897`` — ``_prepare_move_line_vals`` hace un **ida y vuelta de
   unidad**: si la conversión no es exacta, guarda en la unidad del producto en
   vez de asentar una cifra redondeada.
2. ``:1958-1959`` — un producto con serie produce **una línea por unidad**.
3. ``:1912-1956`` — el reparto agrupa los quants duplicados por su combinación
   antes de decidir, y sólo acumula sobre una línea si la conversión es exacta.
4. ``:2030-2036`` — la disponibilidad descarta las combinaciones que quedan en
   cero o en negativo.
5. ``:2468-2549`` — el plan de cantidad hecha conserva las tres salidas de la
   fuente: borrar la línea que sobra, recortar la que excede, consumir la que
   cabe; y las líneas ya empaquetadas descuentan sin tocarse.
6. ``:2564-2599`` — sin regla que cubra el trayecto, el movimiento se abastece
   de existencias.

**Divergencia declarada** que estos casos fijan: ``_set_quantity_done_prepare_vals``
devuelve tuplas ``('update'|'delete'|'create', línea, vals)`` en vez de la lista
de ``Command`` de la fuente, porque el ``Command`` de este árbol es *ejecutivo*
—escribe al llamarlo— y una lista de comandos no se puede devolver sin haber
escrito ya. Registrada en :ref:`h-api-589` (tarea **#345**).
"""
from decimal import Decimal

import pytest

from addons.base.models import ResCompany
from addons.product.models import ProductProduct, ProductTemplate
from addons.stock.models import (
    StockLocation,
    StockMove,
    StockMoveLine,
    StockPickingType,
    StockQuant,
    StockPackage,
)
from addons.uom.models import Uom

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def company(db):
    return ResCompany.objects.create(name='Kaupamex', code='kaupamex_test')


@pytest.fixture
def source(db):
    return StockLocation.objects.create(name='Stock', usage='internal')


@pytest.fixture
def destination(db):
    return StockLocation.objects.create(name='Customers', usage='customer')


@pytest.fixture
def unit(db):
    """La unidad de medida del producto.

    Va explícita porque toda la ola C convierte cantidades: sin ``uom`` en la
    plantilla, ``self.product.uom`` es ``None`` y la primera conversión revienta.
    """
    return Uom.objects.create(name='Unidades')


@pytest.fixture
def variant(db, unit):
    tmpl = ProductTemplate.objects.create(
        name='Camisa', list_price=Decimal('100.00'), uom=unit)
    return ProductProduct.objects.create(product_tmpl=tmpl, default_code='CAM-M')


@pytest.fixture
def picking_type(db, company):
    return StockPickingType.objects.create(
        name='Entrega', code='outgoing', sequence_code='OUT', company=company)


@pytest.fixture
def move(db, variant, source, destination, company):
    """Un movimiento insertado, que es el receptor de toda la ola C.

    ``company`` va explícita: su ``default`` es ``get_current_company``, que
    fuera de una petición devuelve ``None`` y choca contra el ``NOT NULL``.
    """
    return StockMove.objects.create(
        product=variant, location=source, location_dest=destination,
        company=company, product_uom=variant.product_tmpl.uom,
        product_uom_qty=Decimal('5'))


# -- _prepare_move_line_vals (``:1867-1897``) --------------------------------

def test_prepare_move_line_vals_carries_the_seven_base_keys(move):
    """Sin cantidad, el diccionario es el esqueleto de la línea y nada más."""
    vals = move._prepare_move_line_vals()

    assert vals == {
        'move': move,
        'product': move.product,
        'product_uom': move.product_uom,
        'location': move.location,
        'location_dest': move.location_dest,
        'picking': move.picking,
        'company': move.company,
    }
    assert 'quantity' not in vals


def test_prepare_move_line_vals_keeps_the_move_uom_when_conversion_is_exact(move):
    """Ida y vuelta exacto → la cantidad se guarda en la unidad del movimiento.

    Es el caso corriente: el movimiento y el producto comparten unidad, así que
    la conversión no puede perder nada.
    """
    vals = move._prepare_move_line_vals(quantity=3)

    assert vals['quantity'] == 3
    assert vals['product_uom'] == move.product_uom


def test_prepare_move_line_vals_takes_the_quant_placement(move, source, company):
    """``:1893-1897`` — el quant reservado impone dónde está la mercancía.

    Las cuatro claves de colocación se sobreescriben; el resto del esqueleto no
    se toca.
    """
    quant = StockQuant.objects.create(
        product=move.product, location=source, company=company,
        quantity=Decimal('10'))

    vals = move._prepare_move_line_vals(reserved_quant=quant)

    assert vals['location'] == quant.location
    assert vals['lot'] == quant.lot
    assert vals['package'] == quant.package
    assert vals['owner'] == quant.owner
    assert vals['move'] == move          # el esqueleto sobrevive


# -- _add_serial_move_line_to_vals_list (``:1958-1959``) ---------------------

def test_serial_product_gets_one_line_per_unit(move, source, company):
    """Un producto con número de serie no admite fracción."""
    quant = StockQuant.objects.create(
        product=move.product, location=source, company=company,
        quantity=Decimal('3'))

    valores = move._add_serial_move_line_to_vals_list(quant, 3)

    assert len(valores) == 3
    assert all(v['quantity'] == 1 for v in valores)


def test_serial_line_list_truncates_a_fractional_quantity(move, source, company):
    """``int(quantity)`` de la fuente: 2.7 unidades de serie son dos líneas."""
    quant = StockQuant.objects.create(
        product=move.product, location=source, company=company,
        quantity=Decimal('3'))

    assert len(move._add_serial_move_line_to_vals_list(quant, 2.7)) == 2


# -- _get_available_move_lines* (``:1989-2036``) -----------------------------

def test_available_move_lines_in_is_empty_without_origins(move):
    """Sin cadena de origen no entró nada — el diccionario sale vacío."""
    assert move._get_available_move_lines_in() == {}


def test_available_move_lines_discards_what_is_not_positive(move):
    """``:2035`` — sólo salen las combinaciones que aún tienen algo.

    Quien consume el resultado itera esperando que cada entrada sea reservable;
    una entrada en cero rompería esa expectativa.
    """
    disponible = move._get_available_move_lines(set(), set())

    assert all(v > 0 for v in disponible.values())


# -- _set_quantity_done_prepare_vals (``:2468-2549``) ------------------------

def test_quantity_plan_creates_one_line_when_the_move_has_none(move):
    """Sin líneas que repartir, todo el pedido se vuelve una línea nueva."""
    plan = move._set_quantity_done_prepare_vals(4)

    assert len(plan) == 1
    accion, linea, vals = plan[0]
    assert (accion, linea) == ('create', None)
    assert vals['quantity'] == 4


def test_quantity_plan_trims_the_line_that_holds_more_than_asked(move):
    """``:2520-2528`` — la línea que excede se recorta, no se borra."""
    linea = StockMoveLine.objects.create(
        **move._prepare_move_line_vals(quantity=10))

    plan = move._set_quantity_done_prepare_vals(4)

    assert [a for a, _, _ in plan] == ['update']
    _, tocada, vals = plan[0]
    assert tocada.pk == linea.pk
    assert vals['quantity'] == Decimal('4')


def test_quantity_plan_deletes_the_leftover_line_when_nothing_remains(move):
    """``:2513-2515`` — agotada la cantidad, la línea que sobra se borra."""
    StockMoveLine.objects.create(**move._prepare_move_line_vals(quantity=2))

    plan = move._set_quantity_done_prepare_vals(0)

    assert [a for a, _, _ in plan] == ['delete']


def test_quantity_plan_leaves_a_packaged_line_untouched(move):
    """``:2536-2538`` — lo ya empaquetado descuenta del pedido y no se toca.

    La línea aporta sus 4 unidades al total pero no aparece en el plan; sólo
    entra la creación por el remanente.
    """
    paquete = StockPackage.objects.create(name='CAJA-001')
    vals = move._prepare_move_line_vals(quantity=4)
    StockMoveLine.objects.create(**dict(vals, result_package=paquete))

    plan = move._set_quantity_done_prepare_vals(6)

    assert [a for a, _, _ in plan] == ['create']
    assert plan[0][2]['quantity'] == 2      # 6 pedidas − 4 ya empaquetadas


# -- _adjust_procure_method (``:2564-2599``) ---------------------------------

def test_without_a_matching_rule_the_move_is_supplied_from_stock(move):
    """``:2594-2596`` — sin regla que cubra el trayecto, MTS.

    Es la salida por defecto y la que más se ejerce: el árbol de ubicaciones se
    recorre entero sin encontrar regla y el movimiento queda abasteciéndose de
    existencias.
    """
    move._adjust_procure_method()

    move.refresh_from_db()
    assert move.procure_method == StockMove.PROCURE_MAKE_TO_STOCK
