"""Contrato de ``partner_ids`` en ``stock.lot`` — desbloqueado en la tarea #390.

Fiel a ``odoo19c: addons/stock/models/stock_lot.py`` (``odoo-tools@622ddc2a``,
LGPL-3), líneas 58 (campo), 159-166 (``_compute_partner_ids``) y 265-291
(``_search_partner_ids``). Los tres símbolos quedaban **BLOQUEADOS** en el
porte previo porque ``StockPicking`` aún no declaraba ``partner``; ya lo
declara (``stock_picking.py:1139``), así que este archivo es el TDD del
desbloqueo.

Los dos invariantes que estos casos fijan:

1. ``partner_ids`` recoge los contactos de las entregas **hechas** y
   **salientes** del lote, sin repetir, con la más reciente primero.
   **DIVERGENCIA declarada** (misma que documenta ``stock_lot.py``): la
   fuente ordena por ``date_done``; aquí no existe ese campo en
   ``StockPicking``, así que se ordena por ``pk`` descendente.
2. ``_search_partner_ids`` es la búsqueda masiva equivalente — incluido el
   caso invertido ``('in', [False])``, que busca «sin contacto» localizando
   primero a los que SÍ tienen uno.
"""
from decimal import Decimal

import pytest

from addons.base.models import ResCompany, ResPartner
from addons.product.models import ProductProduct, ProductTemplate
from addons.stock.models import (
    StockLocation,
    StockLot,
    StockMove,
    StockMoveLine,
    StockPicking,
    StockPickingType,
)
from addons.uom.models import Uom

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def company(db):
    return ResCompany.objects.create(name='Kaupamex', code='kaupamex_test')


@pytest.fixture
def unit(db):
    return Uom.objects.create(name='Unidades')


@pytest.fixture
def source(db):
    return StockLocation.objects.create(name='Stock', usage='internal')


@pytest.fixture
def destination(db):
    return StockLocation.objects.create(name='Customers', usage='customer')


@pytest.fixture
def variant(db, unit):
    tmpl = ProductTemplate.objects.create(
        name='Motor', list_price=Decimal('900.00'), uom=unit, tracking='serial')
    return ProductProduct.objects.create(product_tmpl=tmpl, default_code='MOT-1')


@pytest.fixture
def outgoing_type(db, company):
    return StockPickingType.objects.create(
        name='Entrega', code='outgoing', sequence_code='OUT', company=company)


@pytest.fixture
def make_delivery(db, source, destination, company, variant, outgoing_type):
    """Fabrica una entrega **hecha** de ``variant`` a un contacto, con lote.

    Devuelve el ``StockPicking``. Encapsula la cadena picking→move→move_line
    que ``_get_outgoing_domain`` necesita ver: tipo de operación saliente y
    estado hecho.
    """
    def _make(lot, partner=None, quantity=Decimal('1')):
        picking = StockPicking.objects.create(
            picking_type=outgoing_type, company=company, partner=partner,
            state=StockPicking.STATE_DONE)
        move = StockMove.objects.create(
            product=variant, location=source, location_dest=destination,
            company=company, product_uom=variant.product_tmpl.uom,
            product_uom_qty=quantity, picking=picking,
            state=StockMove.STATE_DONE)
        StockMoveLine.objects.create(
            move=move, picking=picking, product=variant,
            product_uom=variant.product_tmpl.uom, location=source,
            location_dest=destination, company=company, lot=lot,
            quantity=quantity)
        return picking
    return _make


@pytest.fixture
def make_lot(db, company, variant):
    def _make(name):
        return StockLot.objects.create(name=name, product=variant, company=company)
    return _make


# -- partner_ids / _compute_partner_ids (``:58``, ``:159-166``) --------------

def test_partner_ids_is_empty_without_deliveries(make_lot):
    """Sin entregas, la lista de contactos es vacía — no ``None``."""
    lot = make_lot('SN-000')
    assert lot.partner_ids == []


def test_partner_ids_collects_the_contacts_of_its_deliveries(
        make_lot, make_delivery):
    """``:159-163`` — el contacto de cada entrega hecha, sin repetir."""
    lot = make_lot('SN-001')
    receptor = ResPartner.objects.create(name='Receptor Uno')
    make_delivery(lot, partner=receptor)

    assert lot.partner_ids == [receptor.pk]


def test_partner_ids_orders_most_recent_delivery_first(make_lot, make_delivery):
    """DIVERGENCIA declarada: se ordena por ``pk`` descendente (no hay
    ``date_done`` en este árbol) — la entrega creada después sale primero."""
    lot = make_lot('SN-002')
    primero = ResPartner.objects.create(name='Receptor Antiguo')
    segundo = ResPartner.objects.create(name='Receptor Reciente')
    make_delivery(lot, partner=primero)
    make_delivery(lot, partner=segundo)

    assert lot.partner_ids == [segundo.pk, primero.pk]


def test_partner_ids_ignores_delivery_without_partner(make_lot, make_delivery):
    """``:163-165`` — ``partner_ids = False`` cuando la entrega no trae
    contacto; aquí se traduce a que esa entrega no aporte ningún id."""
    lot = make_lot('SN-003')
    make_delivery(lot, partner=None)

    assert lot.partner_ids == []
    assert lot.delivery_count == 1   # la entrega sí se contó como tal


# -- _search_partner_ids (``:265-291``) ---------------------------------------

def test_search_partner_ids_rejects_negative_operators(make_lot):
    """``Domain.NEGATIVE_OPERATORS`` corta antes de construir nada."""
    assert StockLot._search_partner_ids('!=', [1]) is NotImplemented


def test_search_partner_ids_rejects_non_iterable_value(make_lot):
    """El valor debe ser iterable — un entero suelto no lo es."""
    assert StockLot._search_partner_ids('=', 5) is NotImplemented


def test_search_partner_ids_matches_lot_by_contact(make_lot, make_delivery):
    """``operator='in'`` con el pk del contacto encuentra el lote."""
    lot_with_contact = make_lot('SN-010')
    sin_entregas = make_lot('SN-011')
    receptor = ResPartner.objects.create(name='Receptor Búsqueda')
    make_delivery(lot_with_contact, partner=receptor)

    encontrados = StockLot.ids_matching_partner_ids('in', [receptor.pk])

    assert list(encontrados) == [lot_with_contact]
    assert sin_entregas not in encontrados


def test_search_partner_ids_inverted_case_finds_lots_without_contact(
        make_lot, make_delivery):
    """``operator='in'`` con ``[False]`` — el caso invertido de la fuente.

    Se localizan primero los lotes que SÍ tienen contacto de entrega, y se
    devuelven los que no están ahí — incluidos los que no tienen ninguna
    entrega en absoluto.
    """
    lot_with_contact = make_lot('SN-020')
    sin_contacto = make_lot('SN-021')
    sin_entregas = make_lot('SN-022')
    receptor = ResPartner.objects.create(name='Receptor Invertido')
    make_delivery(lot_with_contact, partner=receptor)
    make_delivery(sin_contacto, partner=None)

    lots_without_delivery_contact = StockLot.ids_matching_partner_ids('in', [False])

    assert lot_with_contact not in lots_without_delivery_contact
    assert sin_contacto in lots_without_delivery_contact
    assert sin_entregas in lots_without_delivery_contact
