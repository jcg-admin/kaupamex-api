"""Tests — el motor de cantidades que ``stock`` cuelga de ``product.product``.

Cubre el bloque ``odoo19c: stock/models/product.py:146-536``: los cinco campos
de cantidad, sus cinco buscadores y los dos resolutores de ubicación.

El eje que se ejercita es el que la referencia declara primero y el que más
consumidores tiene: ``qty_available`` alimenta al orderpoint, al reaprovisiona-
miento y al informe de previsión, y su valor depende por completo de qué
ubicaciones entran en el conjunto — de ahí que la mitad de estas pruebas midan
``_get_domain_locations`` antes que la cantidad misma.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.base.models import ResCompany
from addons.product.models import ProductCategory, ProductProduct
from addons.stock.models import (StockLocation, StockMove, StockQuant,
                                 StockRoute, StockWarehouse)
from exceptions import UserError
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.integration


def _location(name, parent=None, usage=StockLocation.USAGE_INTERNAL):
    return StockLocation.objects.create(name=name, location=parent, usage=usage)


def _quant(product, location, qty, reserved=0):
    return StockQuant.objects.create(
        product=product, location=location, quantity=Decimal(str(qty)),
        reserved_quantity=Decimal(str(reserved)))


def _move(product, source, dest, qty, state='confirmed', moment=None):
    move = StockMove.objects.create(
        product=product, product_uom=product.uom,
        product_uom_qty=Decimal(str(qty)), product_qty=Decimal(str(qty)),
        quantity=Decimal(str(qty)), location=source, location_dest=dest,
        state=state)
    if moment is not None:
        StockMove.objects.filter(pk=move.pk).update(date=moment)
        move.refresh_from_db()
    return move


@pytest.fixture
def tree(db):
    """Vista → estantería → repisa, más un proveedor y un cliente afuera."""
    view = _location('WH', usage=StockLocation.USAGE_VIEW)
    stock = _location('WH/Stock', parent=view)
    shelf = _location('WH/Stock/Shelf 1', parent=stock)
    supplier = _location('Vendors', usage=StockLocation.USAGE_SUPPLIER)
    customer = _location('Customers', usage=StockLocation.USAGE_CUSTOMER)
    return {'view': view, 'stock': stock, 'shelf': shelf,
            'supplier': supplier, 'customer': customer}


# === ``_get_domain_locations`` ==============================================


def test_the_set_includes_descendants(tree):
    """≙ el ``child_of`` que la fuente resuelve con un CTE recursivo.

    Aquí lo da ``parent_path``: una existencia en el nieto cuenta para la
    vista, sin que nadie enumere los ids intermedios.
    """
    product = make_product(name='With grandchild')
    _quant(product, tree['shelf'], 7)

    values = ProductProduct._compute_quantities(
        [product], location=tree['view'].pk)
    assert values[product.pk]['qty_available'] == 7.0


def test_strict_does_not_walk_down_the_tree(tree):
    """Con ``strict`` la fuente compara por id, sin recorrer el árbol."""
    product = make_product(name='Here only')
    _quant(product, tree['shelf'], 7)

    values = ProductProduct._compute_quantities(
        [product], location=tree['view'].pk, strict=True)
    assert values[product.pk]['qty_available'] == 0.0


def test_the_location_can_be_given_by_name(tree):
    """≙ el ``ilike`` sobre ``_rec_name`` de ``_search_ids`` (``:352-359``)."""
    product = make_product(name='By name')
    _quant(product, tree['stock'], 3)

    values = ProductProduct._compute_quantities([product], location='WH/Stock')
    assert values[product.pk]['qty_available'] == 3.0


def test_without_a_location_the_company_warehouse_rules(tree, active_company):
    """Sin ubicación ni almacén, el conjunto son las vistas de los almacenes.

    El almacén tiene que ser de una empresa **activada**: la rama por defecto
    filtra por ``get_current_companies()`` — ≙ ``self.env.companies``
    (``odoo19c: :388-390``).
    """
    StockWarehouse.objects.create(
        name='Main', code='WH', company=active_company,
        view_location=tree['view'], lot_stock=tree['stock'])
    product = make_product(name='By warehouse')
    _quant(product, tree['stock'], 11)

    assert product.qty_available == 11.0


def test_the_warehouse_of_another_company_does_not_count(tree):
    """La otra mitad del filtro: una empresa no activada no aporta almacenes.

    Es el caso que la fuente resuelve con ``self.env.companies`` y el que hace
    que el aislamiento multi-empresa sea real en el motor de cantidades.
    """
    other = ResCompany.objects.create(name='Kaupamex QA', code='kx-qa')
    StockWarehouse.objects.create(
        name='Foreign', code='WHX', company=other,
        view_location=tree['view'], lot_stock=tree['stock'])
    product = make_product(name='Foreign warehouse')
    _quant(product, tree['stock'], 11)

    assert product.qty_available == 0.0


def test_the_warehouse_can_be_given_by_id(tree):
    company = ResCompany.objects.create(name='Kaupamex QA 2', code='kx-qa2')
    warehouse = StockWarehouse.objects.create(
        name='Secondary', code='WH2', company=company,
        view_location=tree['view'], lot_stock=tree['stock'])
    product = make_product(name='By warehouse id')
    _quant(product, tree['shelf'], 4)

    values = ProductProduct._compute_quantities(
        [product], warehouse=warehouse.pk)
    assert values[product.pk]['qty_available'] == 4.0


def test_an_empty_set_yields_zero_not_everything(db):
    """≙ ``if not location_ids: return (Domain.FALSE,) * 3`` (``:395-396``).

    La rama importa: un ``Q()`` vacío matchea TODO, así que confundirla con
    «sin filtro» daría la existencia del árbol entero.
    """
    product = make_product(name='No set')
    _quant(product, _location('Loose'), 99)

    values = ProductProduct._compute_quantities([product], location=[])
    assert values[product.pk]['qty_available'] == 0.0


# === los cinco campos de cantidad ===========================================


def test_free_qty_subtracts_the_reserved_amount(tree):
    """≙ ``free_qty`` (``odoo19c: :81-91``)."""
    product = make_product(name='Reserved')
    _quant(product, tree['stock'], 10, reserved=4)

    values = ProductProduct._compute_quantities(
        [product], location=tree['view'].pk)
    assert values[product.pk]['qty_available'] == 10.0
    assert values[product.pk]['free_qty'] == 6.0


def test_incoming_and_outgoing_count_pending_moves(tree):
    """Entra lo que llega al conjunto; sale lo que lo abandona."""
    product = make_product(name='In transit')
    _move(product, tree['supplier'], tree['stock'], 5)
    _move(product, tree['stock'], tree['customer'], 2)

    values = ProductProduct._compute_quantities(
        [product], location=tree['view'].pk)
    assert values[product.pk]['incoming_qty'] == 5.0
    assert values[product.pk]['outgoing_qty'] == 2.0


def test_an_internal_move_neither_enters_nor_leaves(tree):
    """El origen Y el destino están dentro: el conjunto no gana ni pierde.

    Es lo que las dos restas de la fuente producen
    (``dest_loc_domain & ~loc_domain`` y ``loc_domain & dest_loc_domain_out``);
    sin ellas un traspaso interno se contaría dos veces.
    """
    product = make_product(name='Internal transfer')
    _move(product, tree['stock'], tree['shelf'], 8)

    values = ProductProduct._compute_quantities(
        [product], location=tree['view'].pk)
    assert values[product.pk]['incoming_qty'] == 0.0
    assert values[product.pk]['outgoing_qty'] == 0.0


def test_virtual_available_is_the_sum_of_the_three(tree):
    """≙ ``virtual_available`` (``odoo19c: :69-79``)."""
    product = make_product(name='Forecast')
    _quant(product, tree['stock'], 10)
    _move(product, tree['supplier'], tree['stock'], 5)
    _move(product, tree['stock'], tree['customer'], 3)

    values = ProductProduct._compute_quantities(
        [product], location=tree['view'].pk)
    assert values[product.pk]['virtual_available'] == 12.0


def test_a_done_move_is_not_pending(tree):
    """Sólo cuentan los cuatro estados pendientes que la fuente enumera."""
    product = make_product(name='Already done')
    _move(product, tree['supplier'], tree['stock'], 5, state='done')

    values = ProductProduct._compute_quantities(
        [product], location=tree['view'].pk)
    assert values[product.pk]['incoming_qty'] == 0.0


def test_a_service_carries_no_stock(tree):
    """≙ el ``filtered(lambda p: p.type != 'service')`` de ``:152``."""
    service = make_product(name='Installation')
    service.product_tmpl.type = 'service'
    service.product_tmpl.save()
    _quant(service, tree['stock'], 42)

    values = ProductProduct._compute_quantities(
        [service], location=tree['view'].pk)
    assert values[service.pk]['qty_available'] == 0.0


def test_the_five_keys_come_out_even_with_nothing(tree):
    """Un producto sin quant ni movimiento devuelve ceros, no un dict vacío."""
    product = make_product(name='Untouched')
    values = ProductProduct._compute_quantities(
        [product], location=tree['view'].pk)
    assert values[product.pk] == {
        'qty_available': 0.0, 'free_qty': 0.0, 'incoming_qty': 0.0,
        'outgoing_qty': 0.0, 'virtual_available': 0.0}


# === el eje temporal ========================================================


def test_a_past_to_date_undoes_what_was_done_after_it(tree):
    """≙ la rama ``dates_in_the_past`` (``odoo19c: :224-234``).

    Preguntar «cuánto había ayer» es tomar lo de hoy y deshacer los
    movimientos hechos desde entonces — no volver a sumarlos.
    """
    product = make_product(name='Retrospective')
    _quant(product, tree['stock'], 10)
    _move(product, tree['supplier'], tree['stock'], 4, state='done',
          moment=timezone.now() - timedelta(hours=1))

    yesterday = timezone.now() - timedelta(days=1)
    values = ProductProduct._compute_quantities(
        [product], location=tree['view'].pk, to_date=yesterday)
    assert values[product.pk]['qty_available'] == 6.0


def test_a_future_to_date_undoes_nothing(tree):
    product = make_product(name='Prospective')
    _quant(product, tree['stock'], 10)
    _move(product, tree['supplier'], tree['stock'], 4, state='done',
          moment=timezone.now() - timedelta(hours=1))

    tomorrow = timezone.now() + timedelta(days=1)
    values = ProductProduct._compute_quantities(
        [product], location=tree['view'].pk, to_date=tomorrow)
    assert values[product.pk]['qty_available'] == 10.0


def test_a_bare_date_covers_the_whole_day(tree):
    """≙ ``datetime.combine(to_date.date(), time.max)`` (``:172-174``).

    Sin esta distinción, «hasta el día D» se leería como «hasta las 00:00 del
    día D» y perdería todo lo del propio día.
    """
    product = make_product(name='Whole day')
    _quant(product, tree['stock'], 10)
    _move(product, tree['supplier'], tree['stock'], 4, state='done',
          moment=timezone.now() - timedelta(minutes=5))

    values = ProductProduct._compute_quantities(
        [product], location=tree['view'].pk, to_date=timezone.localdate())
    assert values[product.pk]['qty_available'] == 10.0


# === los buscadores =========================================================


def test_search_qty_available_zero_is_the_shortcut(tree):
    """≙ el atajo de ``_search_qty_available`` (``odoo19c: :465-471``)."""
    with_stock = make_product(name='With stock')
    without_stock = make_product(name='Without stock')
    _quant(with_stock, tree['stock'], 5)

    found = {p.pk for p in ProductProduct.objects.filter(
        ProductProduct._search_qty_available('!=', 0))}
    assert with_stock.pk in found
    assert without_stock.pk not in found

    empty = {p.pk for p in ProductProduct.objects.filter(
        ProductProduct._search_qty_available('=', 0))}
    assert without_stock.pk in empty
    assert with_stock.pk not in empty


def test_search_qty_available_with_an_ordering_operator(tree):
    """Fuera del atajo, el buscador calcula y compara en Python."""
    many = make_product(name='Many')
    few = make_product(name='Few')
    _quant(many, tree['stock'], 10)
    _quant(few, tree['stock'], 1)

    found = {p.pk for p in ProductProduct.objects.filter(
        ProductProduct._search_qty_available(
            '>', 5.0, location=tree['view'].pk))}
    assert many.pk in found
    assert few.pk not in found


def test_search_free_qty_sees_the_reserved_amount(tree):
    """El buscador de ``free_qty`` no es el de ``qty_available``."""
    product = make_product(name='Fully reserved')
    _quant(product, tree['stock'], 10, reserved=10)

    free = {p.pk for p in ProductProduct.objects.filter(
        ProductProduct._search_free_qty('>', 0.0, location=tree['view'].pk))}
    assert product.pk not in free

    on_hand = {p.pk for p in ProductProduct.objects.filter(
        ProductProduct._search_qty_available(
            '>', 0.0, location=tree['view'].pk))}
    assert product.pk in on_hand


def test_the_searcher_rejects_a_non_ordering_operator(db):
    """≙ los dos ``raise UserError`` de ``_search_product_quantity``."""
    with pytest.raises(UserError):
        ProductProduct._search_product_quantity('like', 5.0, 'qty_available')
    with pytest.raises(UserError):
        ProductProduct._search_product_quantity('>', 'five', 'qty_available')


# === rutas ==================================================================


def test_get_total_routes_unions_product_and_category_routes(db):
    """≙ ``get_total_routes`` (``odoo19c: :315-317``).

    Es lo que ``stock.warehouse.orderpoint._compute_rules`` consulta, así que
    este test es el contrato del que cuelga el orderpoint.
    """
    parent_categ = ProductCategory.objects.create(name='Parent')
    child_categ = ProductCategory.objects.create(name='Child',
                                                 parent=parent_categ)
    product = make_product(name='With routes', categ=child_categ)

    from_grandparent = StockRoute.objects.create(name='From the grandparent')
    from_own_categ = StockRoute.objects.create(name='From the category')
    from_template = StockRoute.objects.create(name='From the template')
    from_grandparent.categ_ids.add(parent_categ)
    from_own_categ.categ_ids.add(child_categ)
    from_template.product_ids.add(product.product_tmpl)

    assert set(product.get_total_routes().values_list('pk', flat=True)) == {
        from_grandparent.pk, from_own_categ.pk, from_template.pk}
