"""Contrato de persistencia de ``stock.move`` — ola B del porte.

Fiel a ``odoo19c: addons/stock/models/stock_move.py`` (``odoo-tools@622ddc2a``,
LGPL-3). Cada caso cita la línea de la referencia que fija la regla; el test se
escribe **antes** que la implementación (TDD) porque la referencia ya dice qué
se espera — no hay nada que descubrir, sólo que replicar.

Los cinco invariantes que la ola B tiene que sostener:

1. ``:819-831`` — ``create`` normaliza tres cosas antes de insertar: descarta
   ``lot_ids`` cuando ya viene cantidad, hereda el estado del albarán hecho, y
   marca ``picked`` en todo movimiento que nazca hecho.
2. ``:833-906`` — ``write`` prohíbe tocar la cantidad de un movimiento
   cancelado y la unidad de uno hecho.
3. ``:2337-2343`` — ``unlink`` borra primero las líneas y sólo entonces la
   fila; un movimiento encadenado no cancelado se rehúsa a desaparecer.
4. ``:771-784`` — ``default_get`` marca ``additional`` cuando el albarán de
   destino ya pasó de borrador, que es lo que dispara la auto-confirmación.
5. ``:787-792`` — el nombre visible es ``origen/código: origen>destino``.
"""
from decimal import Decimal

import pytest

from addons.base.models import ResCompany
from addons.product.models import ProductProduct, ProductTemplate
from addons.stock.models import (
    StockLocation,
    StockMove,
    StockPicking,
    StockPickingType,
)
from exceptions import UserError

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
def variant(db):
    tmpl = ProductTemplate.objects.create(name='Camisa', list_price=Decimal('100.00'))
    return ProductProduct.objects.create(product_tmpl=tmpl, default_code='CAM-M')


@pytest.fixture
def picking_type(db, company):
    return StockPickingType.objects.create(
        name='Entrega', code='outgoing', sequence_code='OUT', company=company)


def _move(variant, source, destination, company, **extra):
    """El diccionario mínimo con el que un ``stock.move`` es insertable.

    ``company`` va explícita: su ``default`` es ``get_current_company``, que
    fuera de una petición devuelve ``None`` y choca contra el ``NOT NULL``.
    """
    values = dict(product=variant, location=source, location_dest=destination,
                  company=company, product_uom=variant.product_tmpl.uom,
                  product_uom_qty=Decimal('5'))
    values.update(extra)
    return values


# -- 1. create ---------------------------------------------------------------

def test_create_drops_lot_ids_when_quantity_comes_along(
        company, variant, source, destination):
    """``:820-821`` — con cantidad, ``lot_ids`` sobra y la fuente lo descarta.

    Es una normalización, no una validación: la cantidad ya fija qué se movió,
    y dejar ambos permitiría dos verdades distintas sobre lo mismo.
    """
    values = _move(variant, source, destination, company,
                   quantity=Decimal('3'), lot_ids=[1, 2])
    limpio = StockMove._normalize_create_values(values)
    assert 'lot_ids' not in limpio


def test_create_keeps_lot_ids_without_quantity(
        company, variant, source, destination):
    """El descarte es condicional: sin cantidad, ``lot_ids`` es la única señal."""
    values = _move(variant, source, destination, company, lot_ids=[1, 2])
    limpio = StockMove._normalize_create_values(values)
    assert limpio['lot_ids'] == [1, 2]


def test_create_inherits_done_state_from_its_picking(
        company, variant, source, destination, picking_type):
    """``:823-824`` — un movimiento que nace en un albarán hecho nace hecho.

    Sin esto el albarán quedaría con un movimiento en borrador dentro de una
    transferencia ya validada, y su estado derivado retrocedería.
    """
    picking = StockPicking.objects.create(
        name='WH/OUT/0001', state=StockPicking.STATE_DONE,
        picking_type=picking_type, location=source, location_dest=destination)
    values = _move(variant, source, destination, company, picking=picking)
    limpio = StockMove._normalize_create_values(values)
    assert limpio['state'] == StockMove.STATE_DONE


def test_create_marks_picked_when_born_done(
        company, variant, source, destination):
    """``:825-826`` — todo movimiento hecho está recogido por definición."""
    values = _move(variant, source, destination, company, state=StockMove.STATE_DONE)
    limpio = StockMove._normalize_create_values(values)
    assert limpio['picked'] is True


# -- 2. write ----------------------------------------------------------------

def test_write_refuses_quantity_on_a_cancelled_move(
        company, variant, source, destination):
    """``:841-842`` — cambiar la cantidad de un cancelado es un error.

    La fuente pide crear una línea nueva: el cancelado es un hecho histórico y
    reescribirlo borraría por qué se canceló.
    """
    move = StockMove.objects.create(
        **_move(variant, source, destination, company), state=StockMove.STATE_CANCEL)
    with pytest.raises(UserError):
        move.write({'quantity': Decimal('2')})


def test_write_refuses_uom_change_on_a_done_move(
        company, variant, source, destination):
    """``:849-850`` — la unidad de un movimiento hecho es inmutable.

    Cambiarla reinterpretaría una cantidad ya asentada: 5 cajas pasarían a ser
    5 piezas sin que ningún quant se mueva.
    """
    move = StockMove.objects.create(
        **_move(variant, source, destination, company), state=StockMove.STATE_DONE)
    with pytest.raises(UserError):
        move.write({'product_uom': variant.product_tmpl.uom})


def test_write_allows_uom_change_when_conversion_is_skipped(
        company, variant, source, destination):
    """``:849`` — ``skip_uom_conversion`` es la puerta que la fuente deja abierta."""
    move = StockMove.objects.create(
        **_move(variant, source, destination, company), state=StockMove.STATE_DONE)
    move.write({'product_uom': variant.product_tmpl.uom},
               skip_uom_conversion=True)
    assert move.product_uom_id == variant.product_tmpl.uom_id


# -- 3. unlink ---------------------------------------------------------------

def test_unlink_refuses_a_chained_move_that_is_neither_draft_nor_cancel(
        company, variant, source, destination):
    """``:2333-2335`` — borrar un eslabón intermedio dejaría la cadena rota."""
    origen = StockMove.objects.create(
        **_move(variant, source, destination, company), state=StockMove.STATE_DONE)
    destino = StockMove.objects.create(
        **_move(variant, source, destination, company), state=StockMove.STATE_CONFIRMED)
    destino.move_orig_ids.add(origen)
    with pytest.raises(UserError):
        destino.unlink()


def test_unlink_accepts_a_draft_move_with_a_chain(
        company, variant, source, destination):
    """El mismo eslabón en borrador sí se borra: aún no comprometió nada."""
    origen = StockMove.objects.create(**_move(variant, source, destination, company))
    destino = StockMove.objects.create(
        **_move(variant, source, destination, company), state=StockMove.STATE_DRAFT)
    destino.move_orig_ids.add(origen)
    destino.unlink()
    assert not StockMove.objects.filter(pk=destino.pk).exists()


# -- 4. default_get ----------------------------------------------------------

def test_default_get_marks_additional_on_a_confirmed_picking(
        company, source, destination, picking_type):
    """``:779-782`` — en un albarán ya confirmado el movimiento nace adicional.

    ``additional`` es lo que hace que ``_autoconfirm_picking`` lo recoja: sin
    la marca, el movimiento nuevo quedaría en borrador dentro de un albarán en
    marcha.
    """
    picking = StockPicking.objects.create(
        name='WH/OUT/0002', state=StockPicking.STATE_CONFIRMED,
        picking_type=picking_type, location=source, location_dest=destination)
    defaults = StockMove.default_get(['state', 'additional'],
                                     default_picking=picking)
    assert defaults['additional'] is True
    assert 'state' not in defaults


def test_default_get_marks_done_and_additional_on_a_done_picking(
        company, source, destination, picking_type):
    """``:777-779`` — con el albarán hecho el movimiento nace hecho **y** adicional."""
    picking = StockPicking.objects.create(
        name='WH/OUT/0003', state=StockPicking.STATE_DONE,
        picking_type=picking_type, location=source, location_dest=destination)
    defaults = StockMove.default_get(['state', 'additional'],
                                     default_picking=picking)
    assert defaults['state'] == StockMove.STATE_DONE
    assert defaults['additional'] is True


def test_default_get_leaves_a_draft_picking_alone(
        company, source, destination, picking_type):
    """En borrador no hay nada que auto-confirmar: la fuente no marca nada."""
    picking = StockPicking.objects.create(
        name='WH/OUT/0004', state=StockPicking.STATE_DRAFT,
        picking_type=picking_type, location=source, location_dest=destination)
    defaults = StockMove.default_get(['state', 'additional'],
                                     default_picking=picking)
    assert defaults == {}


# -- 5. display_name ---------------------------------------------------------

def test_display_name_joins_origin_code_and_both_locations(
        company, variant, source, destination, picking_type):
    """``:787-792`` — ``origen/código: origen>destino``, con los dos prefijos opcionales."""
    picking = StockPicking.objects.create(
        name='WH/OUT/0005', origin='SO0042', picking_type=picking_type,
        location=source, location_dest=destination)
    move = StockMove.objects.create(
        **_move(variant, source, destination, company), picking=picking)
    assert move.display_name == 'SO0042/CAM-M: Stock>Customers'


def test_display_name_drops_the_prefixes_that_are_absent(
        company, variant, source, destination):
    """Sin albarán y sin código de producto quedan sólo las dos ubicaciones."""
    variant.default_code = ''
    variant.save(update_fields=['default_code'])
    move = StockMove.objects.create(**_move(variant, source, destination, company))
    assert move.display_name == 'Stock>Customers'
