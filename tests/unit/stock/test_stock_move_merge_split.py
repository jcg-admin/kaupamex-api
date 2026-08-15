"""Contrato de fusión, reparto en albarán y división de ``stock.move`` — ola D.

Fiel a ``odoo19c: addons/stock/models/stock_move.py`` (``odoo-tools@622ddc2a``,
LGPL-3). Cada caso cita la línea de la referencia que fija la regla.

Los invariantes que la ola D tiene que sostener:

1. ``:1260-1273`` — al fundir, la cantidad se **suma**; la fecha la decide la
   política de envío del albarán: «lo antes posible» toma la más temprana,
   «todo junto» la más tardía.
2. ``:1302-1321`` — la clave de fusión formatea el decimal a cadena con su
   precisión, para que un error de redondeo no impida una fusión legítima.
3. ``:1355-1370`` — dos movimientos equivalentes del mismo albarán se funden en
   uno, y las líneas del sobrante pasan al superviviente.
4. ``:1372-1392`` — un movimiento **negativo** se absorbe contra el positivo de
   su clave limitada, y el precio unitario se recalcula sobre el valor total.
5. ``:1529-1537`` — un albarán ya **impreso** no admite movimientos nuevos.
6. ``:1651-1677`` — el origen del albarán nuevo concatena hasta cinco documentos
   y corta con puntos suspensivos; el contacto sólo entra si es único.
7. ``:1580-1590`` — al sumar movimientos a un albarán existente, el contacto se
   borra si difieren y los orígenes se acumulan sin repetir.
8. ``:2359-2403`` — dividir un movimiento hecho, cancelado o en borrador es un
   error; dividir uno confirmado baja su cantidad y devuelve los valores del
   pendiente.
9. ``:2314-2330`` — entregar menos de lo pedido crea el pendiente por la
   diferencia.

**Divergencias declaradas** que estos casos fijan: los contextos ``merge_extra``,
``force_split_uom_id`` y ``source_location_id`` de la fuente son **parámetros
explícitos** aquí — este ORM no lleva contexto de entorno en la llamada, mismo
criterio que ``preserve_state``. Y ``_split`` devuelve una lista de
diccionarios, no un recordset: quien llama decide cuándo crear.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.base.models import ResCompany, ResPartner
from addons.product.models import ProductProduct, ProductTemplate
from addons.stock.models import (
    StockLocation,
    StockMove,
    StockMoveLine,
    StockPicking,
    StockPickingType,
    StockReference,
)
from addons.uom.models import Uom
from exceptions import UserError

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
        name='Camisa', list_price=Decimal('100.00'), uom=unit)
    return ProductProduct.objects.create(product_tmpl=tmpl, default_code='CAM-M')


@pytest.fixture
def picking_type(db, company):
    return StockPickingType.objects.create(
        name='Entrega', code='outgoing', sequence_code='OUT', company=company,
        move_type='direct')


@pytest.fixture
def picking(db, company, source, destination, picking_type):
    return StockPicking.objects.create(
        name='WH/OUT/0001', location=source, location_dest=destination,
        picking_type=picking_type, company=company)


@pytest.fixture
def make_move(db, variant, source, destination, company):
    """Fabrica movimientos que sólo difieren en lo que el caso pide."""
    def _make(**extra):
        campos = dict(
            product=variant, location=source, location_dest=destination,
            company=company, product_uom=variant.product_tmpl.uom,
            product_uom_qty=Decimal('5'), state=StockMove.STATE_CONFIRMED,
            date=timezone.now(),
        )
        campos.update(extra)
        return StockMove.objects.create(**campos)
    return _make


# -- _merge_moves_fields (``:1260-1273``) ------------------------------------

def test_merge_fields_adds_up_the_quantities(make_move):
    """Fundir dos movimientos suma lo que piden — no se pierde demanda."""
    uno, dos = make_move(product_uom_qty=Decimal('3')), make_move(product_uom_qty=Decimal('4'))

    valores = uno._merge_moves_fields(moves=[uno, dos])

    assert valores['product_uom_qty'] == Decimal('7')


def test_merge_fields_keeps_the_first_quantity_when_absorbing_an_extra(make_move):
    """``:1268`` — con ``merge_extra`` manda la cantidad del primero."""
    uno, dos = make_move(product_uom_qty=Decimal('3')), make_move(product_uom_qty=Decimal('4'))

    valores = uno._merge_moves_fields(moves=[uno, dos], merge_extra=True)

    assert valores['product_uom_qty'] == Decimal('3')


def test_merge_fields_takes_the_earliest_date_when_shipping_as_soon_as_possible(
        make_move, picking):
    """``:1269`` — con «lo antes posible» el primer envío parcial ya sale."""
    temprano = timezone.now()
    uno = make_move(picking=picking, date=temprano)
    dos = make_move(picking=picking, date=temprano + timedelta(days=3))

    assert uno._merge_moves_fields(moves=[uno, dos])['date'] == temprano


def test_merge_fields_takes_the_latest_date_when_shipping_all_at_once(
        make_move, picking):
    """``:1269`` — con «todo junto» nada sale hasta que todo está."""
    picking.move_type = 'one'
    picking.save(update_fields=['move_type', 'updated_at'])
    temprano = timezone.now()
    tarde = temprano + timedelta(days=3)
    uno = make_move(picking=picking, date=temprano)
    dos = make_move(picking=picking, date=tarde)

    assert uno._merge_moves_fields(moves=[uno, dos])['date'] == tarde


def test_merge_fields_joins_the_distinct_origins(make_move):
    """``:1272`` — el origen del superviviente reúne los de todos, sin repetir."""
    uno = make_move(origin='SO001')
    dos = make_move(origin='SO002')
    tres = make_move(origin='SO001')

    origen = uno._merge_moves_fields(moves=[uno, dos, tres])['origin']

    assert sorted(origen.split('/')) == ['SO001', 'SO002']


# -- _merge_move_itemgetter (``:1302-1321``) ---------------------------------

def test_itemgetter_gives_equivalent_moves_the_same_key(make_move):
    """Dos movimientos que sólo difieren en cantidad son fusionables."""
    uno, dos = make_move(product_uom_qty=Decimal('3')), make_move(product_uom_qty=Decimal('9'))
    clave = uno._merge_move_itemgetter(uno._prepare_merge_moves_distinct_fields())

    assert clave(uno) == clave(dos)


def test_itemgetter_separates_moves_with_a_different_procurement_method(make_move):
    """El método de abastecimiento sí separa: es uno de los campos distintivos."""
    uno = make_move(procure_method=StockMove.PROCURE_MAKE_TO_STOCK)
    dos = make_move(procure_method=StockMove.PROCURE_MAKE_TO_ORDER)
    clave = uno._merge_move_itemgetter(uno._prepare_merge_moves_distinct_fields())

    assert clave(uno) != clave(dos)


def test_itemgetter_formats_the_price_so_rounding_noise_does_not_split(make_move):
    """``:1314-1319`` — el decimal entra como cadena redondeada, no como número.

    Dos precios que difieren por debajo de la precisión publicada deben caer en
    la misma clave: la fuente formatea justo para que el ruido de redondeo no
    impida una fusión legítima.
    """
    uno = make_move(price_unit=Decimal('10.001'))
    dos = make_move(price_unit=Decimal('10.002'))
    clave = uno._merge_move_itemgetter(['price_unit'])

    assert clave(uno) == clave(dos)


def test_itemgetter_drops_the_excluded_field(make_move):
    """``:1303`` — lo excluido no participa en la clave limitada."""
    move = make_move()
    completa = move._merge_move_itemgetter(['product', 'price_unit'])
    limitada = move._merge_move_itemgetter(['product', 'price_unit'],
                                           ['price_unit'])

    assert len(limitada(move)) == len(completa(move)) - 1


# -- _prepare_merge_moves_distinct_fields (``:1275-1288``) -------------------

def test_distinct_fields_are_all_readable_on_the_move(make_move):
    """Todo campo distintivo tiene que poder leerse — o la clave revienta.

    Es el caso de control de :ref:`h-api-625`: la lista traía dos atributos
    fantasma (``scrapped`` y ``package_level``) que ningún modelo declara.
    """
    move = make_move()

    for campo in move._prepare_merge_moves_distinct_fields():
        assert hasattr(move, campo), f'{campo} no existe en StockMove'


def test_distinct_fields_drop_the_procurement_method_when_absorbing_an_extra(make_move):
    """``:1285-1286`` — con ``merge_extra`` el abastecimiento deja de separar."""
    move = make_move()

    assert 'procure_method' in move._prepare_merge_moves_distinct_fields()
    assert 'procure_method' not in move._prepare_merge_moves_distinct_fields(
        merge_extra=True)


# -- _merge_moves (``:1323-1404``) -------------------------------------------

def test_merge_folds_two_equivalent_moves_of_the_same_picking(make_move, picking):
    """``:1355-1365`` — dos equivalentes quedan en uno, con la suma."""
    uno = make_move(picking=picking, product_uom_qty=Decimal('3'))
    dos = make_move(picking=picking, product_uom_qty=Decimal('4'))

    vivos = uno._merge_moves(moves=[uno, dos])

    assert len(vivos) == 1
    vivos[0].refresh_from_db()
    assert vivos[0].product_uom_qty == Decimal('7')
    assert not StockMove.objects.filter(pk=dos.pk).exists()


def test_merge_moves_the_lines_of_the_absorbed_move(make_move, picking):
    """``:1358`` — las líneas del sobrante pasan al superviviente, no se pierden."""
    uno = make_move(picking=picking)
    dos = make_move(picking=picking)
    linea = StockMoveLine.objects.create(**dos._prepare_move_line_vals(quantity=2))

    vivos = uno._merge_moves(moves=[uno, dos])

    linea.refresh_from_db()
    assert linea.move_id == vivos[0].pk


def test_merge_absorbs_a_negative_move_into_its_positive(make_move, picking):
    """``:1372-1386`` — el negativo se resta del positivo y desaparece."""
    positivo = make_move(picking=picking, product_uom_qty=Decimal('10'))
    negativo = make_move(picking=picking, product_uom_qty=Decimal('-4'))

    positivo._merge_moves(moves=[positivo, negativo])

    positivo.refresh_from_db()
    assert positivo.product_uom_qty == Decimal('6')
    assert not StockMove.objects.filter(pk=negativo.pk).exists()


def test_merge_leaves_a_done_move_alone(make_move, picking):
    """``:1354`` — lo hecho no se funde: su historia ya está asentada."""
    hecho = make_move(picking=picking, state=StockMove.STATE_DONE)
    otro = make_move(picking=picking)

    otro._merge_moves(moves=[hecho, otro])

    hecho.refresh_from_db()
    assert hecho.product_uom_qty == Decimal('5')


# -- reparto en albarán (``:1529-1590``, ``:1651-1677``) ---------------------

def test_assignation_domain_excludes_a_printed_picking(make_move):
    """``:1535`` — un albarán impreso ya se entregó en papel."""
    assert make_move()._search_picking_for_assignation_domain()['printed'] is False


def test_no_picking_is_searched_without_references(make_move):
    """``:1541-1542`` — sin referencia no hay grupo al que sumarse."""
    assert make_move()._search_picking_for_assignation() is None


def test_a_referenced_move_finds_the_matching_picking(make_move, picking):
    """``:1543-1545`` — con la misma referencia y trayecto, el albarán se reusa.

    El albarán tiene que **llevar ya** un movimiento con esa referencia: sus
    ``reference_ids`` son las de sus movimientos, no un campo propio
    (``related`` en la fuente, property aquí). Un albarán vacío no es
    candidato ni allá ni aquí.
    """
    referencia = StockReference.objects.create(name='OUT/0001')
    ya_dentro = make_move(picking=picking, picking_type=picking.picking_type)
    referencia.move_ids.add(ya_dentro)

    move = make_move(picking_type=picking.picking_type)
    referencia.move_ids.add(move)

    assert move._search_picking_for_assignation() == picking


def test_new_picking_values_truncate_the_origin_at_five_documents(make_move):
    """``:1657-1663`` — el origen es una etiqueta para leer, no un índice."""
    moves = [make_move(origin=f'SO{n:03d}') for n in range(7)]

    origen = moves[0]._get_new_picking_values(moves=moves)['origin']

    assert origen.endswith('...')
    assert len(origen.split(',')) == 5


def test_new_picking_values_keep_a_single_shared_partner(make_move, db):
    """``:1664-1665`` — el contacto entra sólo si todo el grupo lo comparte."""
    contacto = ResPartner.objects.create(name='Cliente')
    moves = [make_move(partner=contacto), make_move(partner=contacto)]

    assert moves[0]._get_new_picking_values(moves=moves)['partner'] == contacto


def test_new_picking_values_drop_a_divided_partner(make_move, db):
    """Con contactos distintos ninguno es el correcto: el albarán queda sin él."""
    moves = [make_move(partner=ResPartner.objects.create(name=f'C{n}'))
             for n in range(2)]

    assert moves[0]._get_new_picking_values(moves=moves)['partner'] is None


def test_assign_picking_values_wipes_a_conflicting_partner(make_move, picking, db):
    """``:1582-1583`` — el albarán pasa a referirse a varios; se le quita."""
    picking.partner = ResPartner.objects.create(name='Cliente del albarán')
    picking.save(update_fields=['partner', 'updated_at'])
    move = make_move(partner=ResPartner.objects.create(name='Otro'))

    assert move._assign_picking_values(picking, moves=[move])['partner'] is None


def test_assign_picking_values_accumulate_the_origins_without_repeating(
        make_move, picking):
    """``:1584-1589`` — los orígenes se suman; el ya presente no se duplica."""
    picking.origin = 'SO001'
    picking.save(update_fields=['origin', 'updated_at'])
    uno, dos = make_move(origin='SO001'), make_move(origin='SO002')

    valores = uno._assign_picking_values(picking, moves=[uno, dos])

    assert valores['origin'] == 'SO001,SO002'


def test_assign_picking_creates_one_for_an_unassigned_move(make_move, picking_type):
    """``:1571-1573`` — sin albarán al que sumarse, se crea uno."""
    move = make_move(picking_type=picking_type)

    move._assign_picking(moves=[move])

    move.refresh_from_db()
    assert move.picking_id is not None


def test_assign_picking_does_not_create_one_for_a_negative_move(
        make_move, picking_type):
    """``:1566-1570`` — el negativo se va a revertir; no estrena albarán."""
    negativo = make_move(picking_type=picking_type, product_uom_qty=Decimal('-3'))

    negativo._assign_picking(moves=[negativo])

    negativo.refresh_from_db()
    assert negativo.picking_id is None


# -- división y pendiente (``:2314-2403``) -----------------------------------

def test_splitting_a_done_move_is_an_error(make_move):
    """``:2367-2368`` — lo entregado no se reparte hacia atrás."""
    move = make_move(state=StockMove.STATE_DONE)

    with pytest.raises(UserError):
        move._split(Decimal('2'))


def test_splitting_a_draft_move_is_an_error(make_move):
    """``:2369-2372`` — sin confirmar aún puede sustituirse por otros."""
    move = make_move(state=StockMove.STATE_DRAFT)

    with pytest.raises(UserError):
        move._split(Decimal('2'))


def test_splitting_zero_returns_nothing(make_move):
    """``:2374-2375`` — partir nada no crea un movimiento vacío."""
    assert make_move()._split(Decimal('0')) == []


def test_split_lowers_the_original_and_returns_the_pending_values(make_move):
    """``:2396-2402`` — lo que se lleva el pendiente sale del original."""
    move = make_move(product_uom_qty=Decimal('10'))

    valores = move._split(Decimal('4'))

    move.refresh_from_db()
    assert move.product_uom_qty == Decimal('6')
    assert len(valores) == 1
    assert valores[0]['product_uom_qty'] == Decimal('4')


def test_split_vals_exclude_the_destinations_already_settled(make_move):
    """``:2348`` — un destino hecho o cancelado no espera nada del pendiente."""
    move = make_move()
    vivo = make_move(state=StockMove.STATE_CONFIRMED)
    hecho = make_move(state=StockMove.STATE_DONE)
    move.move_dest_ids.add(vivo, hecho)

    destinos = move._prepare_move_split_vals(Decimal('2'))['move_dest_ids']

    assert [d.pk for d in destinos] == [vivo.pk]


def test_backorder_covers_the_shortfall(make_move):
    """``:2320-2325`` — entregar menos deja pendiente la diferencia."""
    move = make_move(product_uom_qty=Decimal('10'), quantity=Decimal('6'))

    pendientes = move._create_backorder(moves=[move])

    assert len(pendientes) == 1
    assert pendientes[0].product_uom_qty == Decimal('4')


def test_no_backorder_when_everything_was_delivered(make_move):
    """Sin faltante no hay pendiente que crear."""
    move = make_move(product_uom_qty=Decimal('10'), quantity=Decimal('10'))

    assert move._create_backorder(moves=[move]) == []
