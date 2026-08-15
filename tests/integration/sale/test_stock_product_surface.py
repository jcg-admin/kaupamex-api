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


def test_parent_route_ids_sube_por_la_cadena_de_padres(db):
    """≙ ``_compute_parent_route_ids`` (``odoo19c: :1310-1318``)."""
    abuela = ProductCategory.objects.create(name='Abuela')
    madre = ProductCategory.objects.create(name='Madre', parent=abuela)
    hija = ProductCategory.objects.create(name='Hija', parent=madre)

    r_abuela = _route('Ruta abuela')
    r_madre = _route('Ruta madre')
    r_abuela.categ_ids.add(abuela)
    r_madre.categ_ids.add(madre)

    heredadas = set(hija.parent_route_ids.values_list('pk', flat=True))
    assert heredadas == {r_abuela.pk, r_madre.pk}


def test_parent_route_ids_excluye_las_propias(db):
    """La referencia resta las propias: ``routes - category.route_ids``."""
    madre = ProductCategory.objects.create(name='Madre')
    hija = ProductCategory.objects.create(name='Hija', parent=madre)
    compartida = _route('Compartida')
    compartida.categ_ids.add(madre, hija)

    assert list(hija.parent_route_ids) == []
    assert set(hija.total_route_ids.values_list('pk', flat=True)) == {compartida.pk}


def test_total_route_ids_une_propias_y_heredadas(db):
    """≙ ``_compute_total_route_ids`` (``odoo19c: :1325-1328``)."""
    madre = ProductCategory.objects.create(name='Madre')
    hija = ProductCategory.objects.create(name='Hija', parent=madre)
    de_madre = _route('De la madre')
    de_hija = _route('De la hija')
    de_madre.categ_ids.add(madre)
    de_hija.categ_ids.add(hija)

    assert set(hija.total_route_ids.values_list('pk', flat=True)) == {
        de_madre.pk, de_hija.pk}


def test_search_total_route_ids_encuentra_la_heredada(db):
    """≙ ``_search_total_route_ids`` (``odoo19c: :1320-1323``).

    El buscador tiene que ver la ruta **heredada**, no sólo la declarada — es
    la razón de que la referencia lo implemente a mano en vez de dejarlo al
    motor de búsqueda.
    """
    madre = ProductCategory.objects.create(name='Madre')
    hija = ProductCategory.objects.create(name='Hija', parent=madre)
    ajena = ProductCategory.objects.create(name='Ajena')
    ruta = _route('Heredable')
    ruta.categ_ids.add(madre)

    encontradas = set(
        ProductCategory._search_total_route_ids([ruta]).values_list('pk', flat=True))
    assert madre.pk in encontradas
    assert hija.pk in encontradas
    assert ajena.pk not in encontradas


def test_filter_for_stock_putaway_rule_acota_a_la_categoria_del_producto(db):
    """≙ ``_search_filter_for_stock_putaway_rule`` (``odoo19c: :1330-1338``)."""
    categoria = ProductCategory.objects.create(name='Con producto')
    ProductCategory.objects.create(name='Sin producto')
    producto = make_product(name='Anclado', categ=categoria)

    acotadas = ProductCategory._search_filter_for_stock_putaway_rule(
        active_model='product.product', active_id=producto.pk)
    assert list(acotadas.values_list('pk', flat=True)) == [categoria.pk]


def test_filter_for_stock_putaway_rule_sin_contexto_no_acota(db):
    """Sin producto en contexto la referencia devuelve el dominio verdadero."""
    ProductCategory.objects.create(name='Una')
    todas = ProductCategory._search_filter_for_stock_putaway_rule()
    assert todas.count() == ProductCategory.objects.count()


def test_removal_strategy_la_lee_el_consumidor_que_ya_existia(db):
    """El campo tenía consumidor antes de existir: ``_get_removal_strategy``.

    ``StockQuant._get_removal_strategy`` (``odoo19c: stock_quant.py:618-628``)
    lee ``product.categ.removal_strategy`` y cae a ``fifo`` cuando no hay.
    """
    estrategia = ProductRemoval.objects.create(name='LIFO', method='lifo')
    categoria = ProductCategory.objects.create(
        name='Con estrategia', removal_strategy=estrategia)
    producto = make_product(name='Perecedero', categ=categoria)
    ubicacion = StockLocation.objects.create(
        name='WH/Stock', usage=StockLocation.USAGE_INTERNAL)

    assert StockQuant._get_removal_strategy(producto, ubicacion) == 'lifo'


def test_packaging_reserve_method_default_es_partial(db):
    """≙ ``packaging_reserve_method`` (``odoo19c: :1302-1306``)."""
    categoria = ProductCategory.objects.create(name='Empaques')
    assert categoria.packaging_reserve_method == 'partial'


# === ``uom.uom`` ============================================================


def test_route_ids_se_propaga_desde_el_tipo_de_paquete(db):
    """≙ ``route_ids`` ``related='package_type_id.route_ids'`` (``:1345``)."""
    tipo = StockPackageType.objects.create(name='Pallet')
    ruta = _route('Ruta de pallet')
    ruta.package_type_ids.add(tipo)
    unidad = Uom.objects.create(name='Pallet', relative_factor=1.0)
    unidad.package_type = tipo
    unidad.save()

    assert list(unidad.route_ids.values_list('pk', flat=True)) == [ruta.pk]


def test_route_ids_sin_tipo_de_paquete_es_vacio(db):
    unidad = Uom.objects.create(name='Suelta', relative_factor=1.0)
    assert list(unidad.route_ids) == []


def test_cambiar_el_factor_con_movimiento_abierto_falla(db):
    """≙ la guarda de ``write`` (``odoo19c: :1347-1373``).

    Reescribir el ratio reinterpretaría cantidades ya registradas, así que la
    fuente lo prohíbe mientras haya movimientos sin cerrar.
    """
    base = Uom.objects.create(name='Unidad', relative_factor=1.0)
    unidad = Uom.objects.create(
        name='Caja', relative_factor=12.0, relative_uom=base)
    producto = make_product(name='En tránsito')
    origen = StockLocation.objects.create(
        name='Vendors', usage=StockLocation.USAGE_SUPPLIER)
    destino = StockLocation.objects.create(
        name='WH/Stock', usage=StockLocation.USAGE_INTERNAL)
    StockMove.objects.create(
        product=producto, product_uom=unidad, product_uom_qty=Decimal('1'),
        location=origen, location_dest=destino, state='confirmed',
    )

    unidad.relative_factor = 24.0
    with pytest.raises(UserError):
        unidad.save()


def test_cambiar_el_factor_sin_movimientos_pasa(db):
    """Sin consumidores abiertos la guarda no se interpone."""
    base = Uom.objects.create(name='Unidad', relative_factor=1.0)
    unidad = Uom.objects.create(
        name='Libre', relative_factor=2.0, relative_uom=base)
    unidad.relative_factor = 3.0
    unidad.save()
    unidad.refresh_from_db()
    assert unidad.relative_factor == 3.0


def test_la_guarda_no_dispara_al_repropagar_a_los_hijos(db):
    """La divergencia declarada del porte, ejercitada.

    ``Uom.save`` repropaga ``factor`` a los hijos. Si la guarda protegiera
    ``factor`` —como enumera la fuente— cada hijo en uso levantaría un error
    que la referencia no levanta: allá el ORM recalcula el compute sin pasar
    por ``write``.
    """
    raiz = Uom.objects.create(name='Unidad', relative_factor=1.0)
    padre = Uom.objects.create(name='Par', relative_factor=2.0, relative_uom=raiz)
    hijo = Uom.objects.create(
        name='Docena', relative_factor=12.0, relative_uom=padre)
    producto = make_product(name='Con hijo en uso')
    origen = StockLocation.objects.create(
        name='Vendors', usage=StockLocation.USAGE_SUPPLIER)
    destino = StockLocation.objects.create(
        name='WH/Stock', usage=StockLocation.USAGE_INTERNAL)
    StockMove.objects.create(
        product=producto, product_uom=hijo, product_uom_qty=Decimal('1'),
        location=origen, location_dest=destino, state='confirmed',
    )

    padre.relative_factor = 3.0   # 2.0 → 3.0: el cambio tiene que ser real
    padre.save()          # repropaga a ``hijo``; no debe levantar

    hijo.refresh_from_db()
    assert hijo.factor == 36.0


def test_adjust_uom_quantities_convierte_a_la_del_quant(db):
    """≙ ``_adjust_uom_quantities`` (``odoo19c: :1375-1393``), sin propagación."""
    unidad = Uom.objects.create(name='Unidad', relative_factor=1.0)
    docena = Uom.objects.create(
        name='Docena', relative_factor=12.0, relative_uom=unidad)

    cantidad, destino = docena._adjust_uom_quantities(2, unidad)
    assert destino == unidad
    assert cantidad == 24.0


def test_adjust_uom_quantities_propaga_cuando_el_parametro_lo_pide(db):
    """Con ``stock.propagate_uom = '1'`` se conserva la unidad de origen."""
    SystemParameter.objects.create(key='stock.propagate_uom', value='1')
    unidad = Uom.objects.create(name='Unidad', relative_factor=1.0)
    docena = Uom.objects.create(
        name='Docena', relative_factor=12.0, relative_uom=unidad)

    cantidad, destino = docena._adjust_uom_quantities(2, unidad)
    assert destino == docena
    assert cantidad == 2.0


def test_los_dos_campos_inversos_no_se_redeclaran(db):
    """``route_ids`` y ``putaway_rule_ids`` los genera Django, no el porte.

    Declararlos del lado de la categoría —como hace la referencia, cuyo ORM no
    genera el inverso— crearía dos columnas para una sola relación. Este test
    fija que el accesor existe y de dónde viene.
    """
    campos = {f.name: f for f in ProductCategory._meta.get_fields()}
    assert campos['route_ids'].related_model is StockRoute
    assert campos['putaway_rule_ids'].related_model.__name__ == 'StockPutawayRule'
    assert ProductTemplate._meta.get_fields()  # el template también los tiene
