"""Tests — la superficie que ``stock`` cuelga de ``product`` y de ``uom``.

Cubre las dos clases que ``addons/stock/models/product.py`` cierra en este
pase: ``ProductCategory`` (``odoo19c: stock/models/product.py:1278-1338``) y
``UomUom`` (``:1341-1393``).

El eje que se ejercita no es cosmético: ``total_route_ids`` de la categoría es
lo que ``stock.warehouse.orderpoint._compute_rules`` consulta
(``odoo19c: stock/models/stock_orderpoint.py:196``), así que estas pruebas son
el contrato del que cuelga el orderpoint.
"""
from decimal import Decimal

import pytest

from addons.base.models import SystemParameter
from addons.product.models import ProductCategory, ProductTemplate
from addons.stock.models import StockLocation, StockMove, StockQuant, StockRoute
from addons.stock.models.product_strategy import ProductRemoval
from addons.stock.models.stock_package_type import StockPackageType
from addons.uom.models.uom_uom import Uom
from exceptions import UserError
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.integration


def _route(name, **kwargs):
    return StockRoute.objects.create(name=name, **kwargs)


# === ``product.category`` ===================================================


def test_parent_route_ids_walks_up_the_parent_chain(db):
    """≙ ``_compute_parent_route_ids`` (``odoo19c: :1310-1318``)."""
    grandparent = ProductCategory.objects.create(name='Abuela')
    parent_categ = ProductCategory.objects.create(name='Madre', parent=grandparent)
    child_categ = ProductCategory.objects.create(name='Hija', parent=parent_categ)

    grandparent_route = _route('Ruta abuela')
    parent_route = _route('Ruta madre')
    grandparent_route.categ_ids.add(grandparent)
    parent_route.categ_ids.add(parent_categ)

    inherited = set(child_categ.parent_route_ids.values_list('pk', flat=True))
    assert inherited == {grandparent_route.pk, parent_route.pk}


def test_parent_route_ids_excludes_the_own_ones(db):
    """La referencia resta las propias: ``routes - category.route_ids``."""
    parent_categ = ProductCategory.objects.create(name='Madre')
    child_categ = ProductCategory.objects.create(name='Hija', parent=parent_categ)
    shared = _route('Compartida')
    shared.categ_ids.add(parent_categ, child_categ)

    assert list(child_categ.parent_route_ids) == []
    assert set(child_categ.total_route_ids.values_list('pk', flat=True)) == {shared.pk}


def test_total_route_ids_unions_own_and_inherited(db):
    """≙ ``_compute_total_route_ids`` (``odoo19c: :1325-1328``)."""
    parent_categ = ProductCategory.objects.create(name='Madre')
    child_categ = ProductCategory.objects.create(name='Hija', parent=parent_categ)
    from_parent = _route('De la madre')
    from_child = _route('De la hija')
    from_parent.categ_ids.add(parent_categ)
    from_child.categ_ids.add(child_categ)

    assert set(child_categ.total_route_ids.values_list('pk', flat=True)) == {
        from_parent.pk, from_child.pk}


def test_search_total_route_ids_finds_the_inherited_one(db):
    """≙ ``_search_total_route_ids`` (``odoo19c: :1320-1323``).

    El buscador tiene que ver la ruta **heredada**, no sólo la declarada — es
    la razón de que la referencia lo implemente a mano en vez de dejarlo al
    motor de búsqueda.
    """
    parent_categ = ProductCategory.objects.create(name='Madre')
    child_categ = ProductCategory.objects.create(name='Hija', parent=parent_categ)
    unrelated = ProductCategory.objects.create(name='Ajena')
    route = _route('Heredable')
    route.categ_ids.add(parent_categ)

    found = set(
        ProductCategory._search_total_route_ids([route]).values_list('pk', flat=True))
    assert parent_categ.pk in found
    assert child_categ.pk in found
    assert unrelated.pk not in found


def test_filter_for_stock_putaway_rule_narrows_to_the_product_category(db):
    """≙ ``_search_filter_for_stock_putaway_rule`` (``odoo19c: :1330-1338``)."""
    category = ProductCategory.objects.create(name='Con producto')
    ProductCategory.objects.create(name='Sin producto')
    product = make_product(name='Anclado', categ=category)

    narrowed = ProductCategory._search_filter_for_stock_putaway_rule(
        active_model='product.product', active_id=product.pk)
    assert list(narrowed.values_list('pk', flat=True)) == [category.pk]


def test_filter_for_stock_putaway_rule_without_context_narrows_nothing(db):
    """Sin producto en contexto la referencia devuelve el dominio verdadero."""
    ProductCategory.objects.create(name='Una')
    every = ProductCategory._search_filter_for_stock_putaway_rule()
    assert every.count() == ProductCategory.objects.count()


def test_removal_strategy_is_read_by_the_consumer_that_already_existed(db):
    """El campo tenía consumidor antes de existir: ``_get_removal_strategy``.

    ``StockQuant._get_removal_strategy`` (``odoo19c: stock_quant.py:618-628``)
    lee ``product.categ.removal_strategy`` y cae a ``fifo`` cuando no hay.
    """
    strategy = ProductRemoval.objects.create(name='LIFO', method='lifo')
    category = ProductCategory.objects.create(
        name='Con estrategia', removal_strategy=strategy)
    product = make_product(name='Perecedero', categ=category)
    location = StockLocation.objects.create(
        name='WH/Stock', usage=StockLocation.USAGE_INTERNAL)

    assert StockQuant._get_removal_strategy(product, location) == 'lifo'


def test_packaging_reserve_method_defaults_to_partial(db):
    """≙ ``packaging_reserve_method`` (``odoo19c: :1302-1306``)."""
    category = ProductCategory.objects.create(name='Empaques')
    assert category.packaging_reserve_method == 'partial'


# === ``uom.uom`` ============================================================


def test_route_ids_propagates_from_the_package_type(db):
    """≙ ``route_ids`` ``related='package_type_id.route_ids'`` (``:1345``)."""
    package_type = StockPackageType.objects.create(name='Pallet')
    route = _route('Ruta de pallet')
    route.package_type_ids.add(package_type)
    unit = Uom.objects.create(name='Pallet', relative_factor=1.0)
    unit.package_type = package_type
    unit.save()

    assert list(unit.route_ids.values_list('pk', flat=True)) == [route.pk]


def test_route_ids_without_a_package_type_is_empty(db):
    unit = Uom.objects.create(name='Suelta', relative_factor=1.0)
    assert list(unit.route_ids) == []


def test_changing_the_factor_with_an_open_move_fails(db):
    """≙ la guarda de ``write`` (``odoo19c: :1347-1373``).

    Reescribir el ratio reinterpretaría cantidades ya registradas, así que la
    fuente lo prohíbe mientras haya movimientos sin cerrar.
    """
    unit_base = Uom.objects.create(name='Unidad', relative_factor=1.0)
    unit = Uom.objects.create(
        name='Caja', relative_factor=12.0, relative_uom=unit_base)
    product = make_product(name='En tránsito')
    source = StockLocation.objects.create(
        name='Vendors', usage=StockLocation.USAGE_SUPPLIER)
    dest = StockLocation.objects.create(
        name='WH/Stock', usage=StockLocation.USAGE_INTERNAL)
    StockMove.objects.create(
        product=product, product_uom=unit, product_uom_qty=Decimal('1'),
        location=source, location_dest=dest, state='confirmed',
    )

    unit.relative_factor = 24.0
    with pytest.raises(UserError):
        unit.save()


def test_changing_the_factor_without_moves_passes(db):
    """Sin consumidores abiertos la guarda no se interpone."""
    unit_base = Uom.objects.create(name='Unidad', relative_factor=1.0)
    unit = Uom.objects.create(
        name='Libre', relative_factor=2.0, relative_uom=unit_base)
    unit.relative_factor = 3.0
    unit.save()
    unit.refresh_from_db()
    assert unit.relative_factor == 3.0


def test_the_guard_does_not_fire_when_repropagating_to_children(db):
    """La divergencia declarada del porte, ejercitada.

    ``Uom.save`` repropaga ``factor`` a los hijos. Si la guarda protegiera
    ``factor`` —como enumera la fuente— cada hijo en uso levantaría un error
    que la referencia no levanta: allá el ORM recalcula el compute sin pasar
    por ``write``.
    """
    root = Uom.objects.create(name='Unidad', relative_factor=1.0)
    parent = Uom.objects.create(name='Par', relative_factor=2.0, relative_uom=root)
    child = Uom.objects.create(
        name='Docena', relative_factor=12.0, relative_uom=parent)
    product = make_product(name='Con hijo en uso')
    source = StockLocation.objects.create(
        name='Vendors', usage=StockLocation.USAGE_SUPPLIER)
    dest = StockLocation.objects.create(
        name='WH/Stock', usage=StockLocation.USAGE_INTERNAL)
    StockMove.objects.create(
        product=product, product_uom=child, product_uom_qty=Decimal('1'),
        location=source, location_dest=dest, state='confirmed',
    )

    parent.relative_factor = 3.0   # 2.0 → 3.0: el cambio tiene que ser real
    parent.save()          # repropaga a ``hijo``; no debe levantar

    child.refresh_from_db()
    assert child.factor == 36.0


def test_adjust_uom_quantities_converts_to_the_quant_unit(db):
    """≙ ``_adjust_uom_quantities`` (``odoo19c: :1375-1393``), sin propagación."""
    unit = Uom.objects.create(name='Unidad', relative_factor=1.0)
    dozen = Uom.objects.create(
        name='Docena', relative_factor=12.0, relative_uom=unit)

    qty, dest = dozen._adjust_uom_quantities(2, unit)
    assert dest == unit
    assert qty == 24.0


def test_adjust_uom_quantities_propagates_when_the_parameter_asks(db):
    """Con ``stock.propagate_uom = '1'`` se conserva la unidad de origen."""
    SystemParameter.objects.create(key='stock.propagate_uom', value='1')
    unit = Uom.objects.create(name='Unidad', relative_factor=1.0)
    dozen = Uom.objects.create(
        name='Docena', relative_factor=12.0, relative_uom=unit)

    qty, dest = dozen._adjust_uom_quantities(2, unit)
    assert dest == dozen
    assert qty == 2.0


def test_the_two_reverse_accessors_are_not_redeclared(db):
    """``route_ids`` y ``putaway_rule_ids`` los genera Django, no el porte.

    Declararlos del lado de la categoría —como hace la referencia, cuyo ORM no
    genera el inverso— crearía dos columnas para una sola relación. Este test
    fija que el accesor existe y de dónde viene.
    """
    fields_by_name = {f.name: f for f in ProductCategory._meta.get_fields()}
    assert fields_by_name['route_ids'].related_model is StockRoute
    assert fields_by_name['putaway_rule_ids'].related_model.__name__ == 'StockPutawayRule'
    assert ProductTemplate._meta.get_fields()  # el template también los tiene
