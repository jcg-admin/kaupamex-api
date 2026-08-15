"""Tests — el resto de ``product.product`` que ``stock`` cuelga.

Cubre el bloque que sigue al motor de cantidades: los contadores de
movimiento, los tres botones de estado, el EAN, el filtro de rutas y la
guarda de cambio de unidad (``odoo19c: stock/models/product.py:292-814``).

El eje que se ejercita es el que la referencia usa para decidir **qué se le
muestra al usuario sobre un producto**: si tiene existencias que ajustar, si
su código de barras es válido, cuántas recepciones y entregas cerró el último
año. Ninguno es cosmético — ``_update_uom`` veta un cambio que
reinterpretaría cantidades ya registradas.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.base.models import ResCompany
from addons.product.models import ProductCategory, ProductProduct
from addons.stock.models import (StockLocation, StockLot, StockMove,
                                 StockMoveLine, StockPicking, StockPickingType,
                                 StockQuant, StockRoute, StockWarehouse)
from addons.uom.models.uom_uom import Uom
from exceptions import UserError
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.integration


def _location(name, usage=StockLocation.USAGE_INTERNAL, parent=None):
    return StockLocation.objects.create(name=name, usage=usage, location=parent)


def _done_line(product, picking_type, source, dest, company):
    """Una línea cerrada bajo un albarán de ese tipo.

    El tipo **no** se pone en la línea: ``picking_type`` es una property que
    lo toma del albarán (``stock_move_line.py:482-490``), fiel al
    ``_compute_picking_type_id`` de la fuente.
    """
    picking = StockPicking.objects.create(
        picking_type=picking_type, location=source, location_dest=dest,
        state='done')
    move = StockMove.objects.create(
        product=product, product_uom=product.uom, product_uom_qty=Decimal('1'),
        location=source, location_dest=dest, state='done', picking=picking)
    return StockMoveLine.objects.create(
        move=move, picking=picking, product=product, product_uom=product.uom,
        quantity=Decimal('1'), location=source, location_dest=dest,
        state='done', company=company)


def _warehouse_for(company, view, stock):
    """El almacén que la rama por defecto de ``_get_domain_locations`` exige."""
    return StockWarehouse.objects.create(
        name='Main', code='WH', company=company,
        view_location=view, lot_stock=stock)


# === contadores de movimiento (``odoo19c: :292-309``) =======================


def test_the_counters_split_receipts_from_deliveries(db, active_company):
    """≙ ``_compute_nbr_moves`` — recepciones y entregas por separado."""
    product = make_product(name='With traffic')
    source = _location('Vendors', StockLocation.USAGE_SUPPLIER)
    dest = _location('WH/Stock')
    incoming = StockPickingType.objects.create(name='Receipts', code='incoming')
    outgoing = StockPickingType.objects.create(name='Delivery', code='outgoing')
    for picking_type, veces in ((incoming, 2), (outgoing, 1)):
        for _ in range(veces):
            _done_line(product, picking_type, source, dest, active_company)

    assert product.nbr_moves_in == 2
    assert product.nbr_moves_out == 1


def test_the_counters_ignore_what_is_older_than_a_year(db, active_company):
    """La fuente acota a un año: ``date >= now - relativedelta(years=1)``."""
    product = make_product(name='Old traffic')
    source = _location('Vendors', StockLocation.USAGE_SUPPLIER)
    dest = _location('WH/Stock')
    picking_type = StockPickingType.objects.create(
        name='Receipts', code='incoming')
    line = _done_line(product, picking_type, source, dest, active_company)
    StockMoveLine.objects.filter(pk=line.pk).update(
        date=timezone.now() - timedelta(days=400))

    assert product.nbr_moves_in == 0


# === los tres botones de estado (``odoo19c: :115-126``) =====================


def test_the_status_buttons_follow_is_storable(db):
    """≙ ``_compute_show_qty_status_button`` — delegan en el template."""
    storable = make_product(name='Storable')
    storable.product_tmpl.is_storable = True
    storable.product_tmpl.save()

    assert storable.show_on_hand_qty_status_button is True
    assert storable.show_forecasted_qty_status_button is True
    assert storable.show_qty_update_button is True


def test_a_product_without_stock_hides_the_buttons(db):
    """Sin existencias que ajustar el botón no tiene destino."""
    service = make_product(name='Not storable')
    service.product_tmpl.is_storable = False
    service.product_tmpl.save()

    assert service.show_on_hand_qty_status_button is False
    assert service.show_qty_update_button is False


# === EAN (``odoo19c: :128-133``) ============================================


def test_a_valid_gtin14_is_reported_as_valid(db):
    """≙ ``_compute_valid_ean`` — el dígito verificador manda."""
    product = make_product(name='With barcode')
    product.barcode = '00000000000017'   # GTIN-14 con verificador correcto
    product.save()

    assert product.valid_ean is True


def test_a_barcode_with_the_wrong_check_digit_is_not_valid(db):
    product = make_product(name='Bad barcode')
    product.barcode = '00000000000019'
    product.save()

    assert product.valid_ean is False


def test_without_a_barcode_there_is_nothing_to_validate(db):
    product = make_product(name='No barcode')
    assert product.valid_ean is False


# === el resto del bloque ====================================================


def test_get_components_returns_the_product_itself(db):
    """≙ ``get_components`` (``odoo19c: :311-313``) — el punto de extensión
    que ``mrp`` sustituye por la lista de materiales."""
    product = make_product(name='Simple')
    assert product.get_components() == [product.pk]


def test_quantity_in_progress_starts_empty(db):
    """≙ ``_get_quantity_in_progress`` — el contrato es el par vacío."""
    product = make_product(name='Nothing in flight')
    entrantes, salientes = product._get_quantity_in_progress()
    assert dict(entrantes) == {} and dict(salientes) == {}


def test_only_qty_available_skips_the_moves(db, active_company):
    """≙ ``_get_only_qty_available`` (``odoo19c: :735-745``).

    Sin argumentos, la fuente resuelve el conjunto con ``self.env.companies``,
    así que la existencia sólo cuenta bajo un almacén de la empresa activada.
    """
    product = make_product(name='On hand only')
    view = _location('WH', StockLocation.USAGE_VIEW)
    stock = _location('WH/Stock', parent=view)
    _warehouse_for(active_company, view, stock)
    StockQuant.objects.create(
        product=product, location=stock, quantity=Decimal('5'))

    assert ProductProduct._get_only_qty_available([product])[product.pk] == 5.0


def test_a_product_with_lots_is_not_offered_for_deletion(db):
    """≙ ``_filter_to_unlink`` (``odoo19c: :747-751``)."""
    with_lot = make_product(name='Tracked')
    free = make_product(name='Untracked')
    StockLot.objects.create(name='SN-1', product=with_lot)

    quedan = ProductProduct._filter_to_unlink([with_lot, free])
    assert [p.pk for p in quedan] == [free.pk]


def test_filter_has_routes_sees_the_inherited_route(db):
    """≙ ``filter_has_routes`` (``odoo19c: :796-805``).

    La segunda mitad —la ruta que viene de la categoría— es la razón de que
    la fuente escriba dos búsquedas en vez de una.
    """
    category = ProductCategory.objects.create(name='With route')
    route = StockRoute.objects.create(name='Heredable')
    route.categ_ids.add(category)
    inherited = make_product(name='By category', categ=category)
    without = make_product(name='Bare')

    con_ruta = ProductProduct.filter_has_routes([inherited, without])
    assert [p.pk for p in con_ruta] == [inherited.pk]


def test_changing_the_uom_with_moves_in_another_unit_is_blocked(db):
    """≙ la guarda de ``_update_uom`` (``odoo19c: :770-794``)."""
    unit = Uom.objects.create(name='Unidad', relative_factor=1.0)
    dozen = Uom.objects.create(
        name='Docena', relative_factor=12.0, relative_uom=unit)
    product = make_product(name='Already moved')
    source = _location('Vendors', StockLocation.USAGE_SUPPLIER)
    dest = _location('WH/Stock')
    StockMove.objects.create(
        product=product, product_uom=dozen, product_uom_qty=Decimal('1'),
        location=source, location_dest=dest, state='confirmed')

    with pytest.raises(UserError):
        product._update_uom(unit)


def test_the_uom_warning_fires_only_with_moves(db):
    """≙ ``_trigger_uom_warning`` (``odoo19c: :807-814``)."""
    quiet = make_product(name='Never moved')
    assert quiet._trigger_uom_warning() is False

    moved = make_product(name='Moved once')
    StockMove.objects.create(
        product=moved, product_uom=moved.uom, product_uom_qty=Decimal('1'),
        location=_location('Vendors', StockLocation.USAGE_SUPPLIER),
        location_dest=_location('WH/Stock'), state='confirmed')
    assert moved._trigger_uom_warning() is True


def test_the_tracking_warning_needs_stock_on_hand(db, active_company):
    """≙ ``_onchange_tracking`` (``odoo19c: :551-556``).

    El aviso cuelga de ``qty_available``, así que exige el mismo almacén de
    empresa activada que el resto del motor.
    """
    product = make_product(name='Tracked with stock')
    product.product_tmpl.tracking = 'lot'
    product.product_tmpl.is_storable = True
    product.product_tmpl.save()
    view = _location('WH', StockLocation.USAGE_VIEW)
    stock = _location('WH/Stock', parent=view)
    _warehouse_for(active_company, view, stock)
    StockQuant.objects.create(
        product=product, location=stock, quantity=Decimal('3'))

    assert product.qty_available == 3.0
    assert product._onchange_tracking() is not None


def test_without_stock_the_tracking_warning_stays_silent(db):
    product = make_product(name='Tracked, empty')
    product.product_tmpl.tracking = 'lot'
    product.product_tmpl.save()
    assert product._onchange_tracking() is None
