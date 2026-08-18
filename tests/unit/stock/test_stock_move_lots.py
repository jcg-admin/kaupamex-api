"""Contrato de lotes y números de serie de ``stock.move`` — ola E.

Fiel a ``odoo19c: addons/stock/models/stock_move.py`` (``odoo-tools@622ddc2a``,
LGPL-3). Cada caso cita la línea de la referencia que fija la regla.

Los invariantes que la ola E tiene que sostener:

1. ``:601-610`` — los lotes de un movimiento son los de sus líneas **con
   cantidad**: una línea a cero no aporta lote, aunque lo lleve puesto.
2. ``:612-620`` — fijar los lotes de un producto sin seguimiento es un no-op;
   y si el movimiento ya está reservado con exactamente esos lotes, tampoco
   hay nada que rehacer.
3. ``:634-643`` — al fijar lotes, una línea cuyo lote **ya no está** en el
   conjunto se borra; una que sí está se reapunta; y una sin lote queda
   disponible para recibir uno.
4. ``:1052-1065`` — generar series exige un contador positivo y produce una
   línea por unidad, con el nombre que la secuencia dicte.
5. ``:1067-1091`` — el nombre de lote se resuelve a lote existente si lo hay, y
   se crea si no; el ``lot_name`` se vacía cuando el lote queda resuelto.
6. ``:1093-1129`` — pegar una lista de lotes la parte por salto de línea, y el
   tabulador (o el punto y coma) separa el nombre de su cantidad.
7. ``:1595-1645`` — al generar líneas de serie se **reusan** primero las líneas
   sin lote, y sólo después se crean nuevas.
8. ``:1449-1520`` — el ajuste de cantidad tras fijar lotes cuenta lo asignable
   más lo ya asignado a los lotes nuevos.

**Divergencias declaradas** que estos casos fijan: ``lot_ids`` es una property
con setter, no un campo ``compute``/``inverse``, porque la fuente lo declara sin
``store``; y los generadores devuelven **tuplas** ``('update'|'create', …)`` en
vez de una lista de ``Command``, por la misma razón que la ola C — el ``Command``
de este árbol es ejecutivo (:ref:`h-api-589`).
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.base.models import ResCompany
from addons.product.models import ProductProduct, ProductTemplate
from addons.stock.models import (
    StockLocation,
    StockLot,
    StockMove,
    StockMoveLine,
    StockPickingType,
)
from addons.uom.models import Uom
from exceptions import UserError, ValidationError

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
def serial_variant(db, unit):
    """Producto con seguimiento por número de serie — una unidad por línea."""
    tmpl = ProductTemplate.objects.create(
        name='Motor', list_price=Decimal('900.00'), uom=unit, tracking='serial')
    return ProductProduct.objects.create(product_tmpl=tmpl, default_code='MOT-1')


@pytest.fixture
def plain_variant(db, unit):
    """Producto sin seguimiento — el caso que ``_set_lot_ids`` ignora."""
    tmpl = ProductTemplate.objects.create(
        name='Camisa', list_price=Decimal('100.00'), uom=unit, tracking='none')
    return ProductProduct.objects.create(product_tmpl=tmpl, default_code='CAM-M')


@pytest.fixture
def picking_type(db, company):
    return StockPickingType.objects.create(
        name='Recepción', code='incoming', sequence_code='IN', company=company,
        move_type='direct', use_create_lots=True, use_existing_lots=False)


@pytest.fixture
def make_move(db, source, destination, company, serial_variant):
    """Fabrica movimientos que sólo difieren en lo que el caso pide."""
    def _make(product=None, **extra):
        product = product or serial_variant
        campos = dict(
            product=product, location=source, location_dest=destination,
            company=company, product_uom=product.product_tmpl.uom,
            product_uom_qty=Decimal('3'), state=StockMove.STATE_CONFIRMED,
            date=timezone.now(),
        )
        campos.update(extra)
        return StockMove.objects.create(**campos)
    return _make


@pytest.fixture
def make_line(db, source, destination, company):
    """Fabrica líneas de movimiento con lote y cantidad explícitos."""
    def _make(move, lot=None, lot_name=None, quantity=Decimal('1')):
        return StockMoveLine.objects.create(
            move=move, product=move.product, product_uom=move.product_uom,
            location=source, location_dest=destination, company=company,
            lot=lot, lot_name=lot_name, quantity=quantity)
    return _make


@pytest.fixture
def make_lot(db, company, serial_variant):
    def _make(name, product=None):
        return StockLot.objects.create(
            name=name, product=product or serial_variant, company=company)
    return _make


# -- lot_ids, la property (``:601-610``) --------------------------------------

def test_lot_ids_collects_the_lots_of_its_lines(make_move, make_line, make_lot):
    """``:604`` — el dominio pide lote puesto y cantidad distinta de cero."""
    move = make_move()
    uno, dos = make_lot('SN-001'), make_lot('SN-002')
    make_line(move, lot=uno)
    make_line(move, lot=dos)

    assert {l.pk for l in move.lot_ids} == {uno.pk, dos.pk}


def test_lot_ids_ignores_a_line_with_zero_quantity(make_move, make_line, make_lot):
    """``:604`` — ``('quantity', '!=', 0.0)``: una línea vacía no aporta lote."""
    move = make_move()
    puesto, vacio = make_lot('SN-001'), make_lot('SN-002')
    make_line(move, lot=puesto, quantity=Decimal('1'))
    make_line(move, lot=vacio, quantity=Decimal('0'))

    assert [l.pk for l in move.lot_ids] == [puesto.pk]


def test_lot_ids_is_empty_without_lines(make_move):
    """Sin líneas no hay lotes — la lista vacía, no ``None``."""
    assert list(make_move().lot_ids) == []


# -- _set_lot_ids (``:612-720``) ----------------------------------------------

def test_setting_lots_on_an_untracked_product_does_nothing(
        make_move, make_line, plain_variant, make_lot):
    """``:620-621`` — ``if move.product_id.tracking == 'none': continue``."""
    move = make_move(product=plain_variant)
    linea = make_line(move)

    move._set_lot_ids([make_lot('SN-001', product=plain_variant)])

    linea.refresh_from_db()
    assert linea.lot_id is None


def test_setting_lots_drops_the_line_whose_lot_left_the_set(
        make_move, make_line, make_lot):
    """``:643`` — ``Command.delete``: el lote que sale se lleva su línea."""
    move = make_move()
    fuera, dentro = make_lot('SN-001'), make_lot('SN-002')
    sobra = make_line(move, lot=fuera)
    make_line(move, lot=dentro)

    move._set_lot_ids([dentro])

    assert not StockMoveLine.objects.filter(pk=sobra.pk).exists()


def test_setting_lots_keeps_the_line_whose_lot_stayed(
        make_move, make_line, make_lot):
    """``:638-641`` — el lote que sigue en el conjunto conserva su línea."""
    move = make_move()
    sigue = make_lot('SN-001')
    linea = make_line(move, lot=sigue)

    move._set_lot_ids([sigue])

    linea.refresh_from_db()
    assert linea.lot_id == sigue.pk


def test_setting_lots_reuses_a_line_without_lot(make_move, make_line, make_lot):
    """``:657-668`` — hay línea libre: se **actualiza**, no se crea otra."""
    move = make_move()
    libre = make_line(move, lot=None)
    nuevo = make_lot('SN-003')

    move._set_lot_ids([nuevo])

    libre.refresh_from_db()
    assert libre.lot_id == nuevo.pk
    assert move.move_line_ids.count() == 1


def test_setting_lots_creates_a_line_when_none_is_free(
        make_move, make_lot):
    """``:669-683`` — sin línea que reusar, nace una por lote."""
    move = make_move()
    uno, dos = make_lot('SN-001'), make_lot('SN-002')

    move._set_lot_ids([uno, dos])

    assert {l.lot_id for l in move.move_line_ids.all()} == {uno.pk, dos.pk}


def test_a_serial_line_carries_exactly_one_unit(make_move, make_lot):
    """``:679-680`` — con seguimiento por serie, la línea vale 1 y no más."""
    move = make_move()

    move._set_lot_ids([make_lot('SN-001')])

    linea = move.move_line_ids.get()
    assert linea.quantity == Decimal('1')


def test_setting_the_same_lots_on_an_assigned_move_is_a_no_op(
        make_move, make_line, make_lot):
    """``:622-623`` — ya reservado con esos lotes: no se rehace nada."""
    move = make_move(state=StockMove.STATE_ASSIGNED)
    lote = make_lot('SN-001')
    linea = make_line(move, lot=lote)
    antes = linea.pk

    move._set_lot_ids([lote])

    assert [l.pk for l in move.move_line_ids.all()] == [antes]


def test_the_setter_of_the_property_delegates(make_move, make_lot):
    """La property y el método son la misma puerta — la fuente lo declara
    ``inverse='_set_lot_ids'`` (``:192``)."""
    move = make_move()
    lote = make_lot('SN-007')

    move.lot_ids = [lote]

    assert [l.pk for l in move.lot_ids] == [lote.pk]


# -- _create_lot_ids_from_move_line_vals (``:1067-1091``) ---------------------

def test_lot_names_resolve_to_the_existing_lot(serial_variant, company, make_lot):
    """``:1070-1074`` — si el nombre ya existe, no se duplica el lote."""
    ya = make_lot('SN-001')
    vals = [{'lot_name': 'SN-001', 'quantity': 1}]

    StockMove._create_lot_ids_from_move_line_vals(
        vals, serial_variant.pk, company.pk)

    assert vals[0]['lot_id'] == ya.pk
    assert StockLot.objects.filter(name='SN-001').count() == 1


def test_an_unknown_lot_name_is_created(serial_variant, company):
    """``:1077-1081`` — el nombre que no existe se crea antes de usarse."""
    vals = [{'lot_name': 'SN-NUEVO', 'quantity': 1}]

    StockMove._create_lot_ids_from_move_line_vals(
        vals, serial_variant.pk, company.pk)

    creado = StockLot.objects.get(name='SN-NUEVO')
    assert vals[0]['lot_id'] == creado.pk


def test_the_lot_name_is_cleared_once_resolved(serial_variant, company):
    """``:1090`` — resuelto el lote, el texto sobra.

    **Divergencia declarada:** la fuente escribe ``False``; aquí ``None``,
    porque estos valores acaban en un ``Char(null=True)`` y un booleano en una
    columna de texto es el defecto que :ref:`h-api-590` registra (tarea #346).
    """
    vals = [{'lot_name': 'SN-NUEVO', 'quantity': 1}]

    StockMove._create_lot_ids_from_move_line_vals(
        vals, serial_variant.pk, company.pk)

    assert vals[0]['lot_name'] is None


def test_vals_without_lot_name_are_left_alone(serial_variant, company):
    """``:1087-1089`` — sin ``lot_name`` no hay nada que resolver."""
    vals = [{'quantity': 2}]

    StockMove._create_lot_ids_from_move_line_vals(
        vals, serial_variant.pk, company.pk)

    assert 'lot_id' not in vals[0]


# -- split_lots (``:1093-1129``) ----------------------------------------------

def test_split_lots_returns_nothing_for_an_empty_string():
    """``:1098-1099`` — sin texto no hay líneas que preparar."""
    assert StockMove.split_lots('') == []


def test_split_lots_breaks_on_newlines():
    """``:1102-1103`` — un nombre por renglón, y los renglones vacíos se caen."""
    salida = StockMove.split_lots('SN-001\nSN-002\n\nSN-003')

    assert [v['lot_name'] for v in salida] == ['SN-001', 'SN-002', 'SN-003']


def test_split_lots_defaults_to_one_unit_per_name():
    """``:1107`` — ``'quantity': 1`` mientras el texto no diga otra cosa."""
    assert StockMove.split_lots('SN-001')[0]['quantity'] == 1


def test_a_tab_separates_the_name_from_its_quantity():
    """``:1112-1120`` — el tabulador trae la cantidad junto al nombre."""
    salida = StockMove.split_lots('LOT-001\t5')

    assert salida[0] == {'lot_name': 'LOT-001', 'quantity': 5.0}


def test_a_semicolon_works_like_a_tab():
    """``:1111-1113`` — «Semicolons are also used for separation»."""
    assert StockMove.split_lots('LOT-001;5')[0]['quantity'] == 5.0


def test_an_unreadable_extra_leaves_the_whole_string_as_the_name():
    """``:1125-1128`` — si la parte extra no se entiende, no se adivina."""
    salida = StockMove.split_lots('LOT-001\tno-es-un-numero')

    assert salida[0]['lot_name'] == 'LOT-001\tno-es-un-numero'


# -- _generate_serial_move_line_commands (``:1595-1645``) ---------------------

def test_serial_commands_reuse_the_lines_without_lot(
        make_move, make_line):
    """``:1618`` — se filtran las líneas sin lote y se **actualizan** primero."""
    move = make_move()
    libre = make_line(move, lot=None)

    ordenes = move._generate_serial_move_line_commands(
        [{'lot_name': 'SN-001', 'quantity': 1}])

    assert ordenes[0][0] == 'update'
    assert ordenes[0][1].pk == libre.pk


def test_serial_commands_create_when_no_line_is_free(make_move):
    """``:1627-1636`` — agotadas las líneas libres, cada nombre crea la suya."""
    move = make_move()

    ordenes = move._generate_serial_move_line_commands(
        [{'lot_name': 'SN-001', 'quantity': 1},
         {'lot_name': 'SN-002', 'quantity': 1}])

    assert [o[0] for o in ordenes] == ['create', 'create']


def test_a_created_serial_line_carries_the_move_coordinates(make_move):
    """``:1612-1617`` — la línea nueva hereda albarán, origen, producto y unidad."""
    move = make_move()

    (_, vals), = move._generate_serial_move_line_commands(
        [{'lot_name': 'SN-001', 'quantity': 1}])

    assert vals['product'] == move.product
    assert vals['location'] == move.location
    assert vals['lot_name'] == 'SN-001'


# -- _generate_serial_numbers (``:1052-1065``) --------------------------------

def test_generating_serials_without_a_count_is_an_error(make_move):
    """``:1058-1059`` — «must be greater than zero»."""
    move = make_move(next_serial_count=0)

    with pytest.raises(ValidationError):
        move._generate_serial_numbers('SN-001')


def test_generating_serials_creates_one_line_per_unit(make_move):
    """``:1060-1064`` — tres series, tres líneas, con los nombres consecutivos."""
    move = make_move()

    move._generate_serial_numbers('SN-001', next_serial_count=3)

    nombres = sorted(l.lot_name for l in move.move_line_ids.all())
    assert nombres == ['SN-001', 'SN-002', 'SN-003']


def test_generating_serials_resolves_the_lot_when_the_type_reuses_lots(
        make_move, picking_type, company):
    """``:1062-1063`` — con ``use_existing_lots`` el nombre se vuelve lote."""
    picking_type.use_existing_lots = True
    picking_type.save()
    move = make_move(picking_type=picking_type)

    move._generate_serial_numbers('SN-100', next_serial_count=2)

    assert StockLot.objects.filter(name__in=['SN-100', 'SN-101']).count() == 2
    assert all(l.lot_id for l in move.move_line_ids.all())


def test_generating_serials_falls_back_to_the_field_count(make_move):
    """``:1057`` — ``next_serial_count or self.next_serial_count``."""
    move = make_move(next_serial_count=2)

    move._generate_serial_numbers('SN-001')

    assert move.move_line_ids.count() == 2


# -- _onchange_lot_ids (``:1449-1520``) ---------------------------------------

def test_the_quantity_adjustment_is_skipped_without_tracking(
        make_move, plain_variant):
    """``:1454-1455`` — sin seguimiento no hay nada que ajustar."""
    move = make_move(product=plain_variant, quantity=Decimal('2'))

    assert move._onchange_lot_ids([]) is None
    assert move.quantity == Decimal('2')


def test_the_quantity_counts_the_lines_already_assigned_to_the_new_lots(
        make_move, make_line, make_lot):
    """``:1464-1466`` — una línea cuyo lote está en el conjunto ya cuenta."""
    move = make_move(quantity=Decimal('0'))
    lote = make_lot('SN-001')
    make_line(move, lot=lote, quantity=Decimal('1'))

    move._onchange_lot_ids([lote])

    assert move.quantity == Decimal('1')


def test_the_quantity_counts_the_assignable_lines(make_move, make_line, make_lot):
    """``:1461-1463`` — la línea sin lote es asignable y suma."""
    move = make_move(quantity=Decimal('0'))
    make_line(move, lot=None, quantity=Decimal('1'))

    move._onchange_lot_ids([make_lot('SN-001')])

    assert move.quantity >= Decimal('1')


# -- action_generate_lot_line_vals (``:1131-1207``) ---------------------------

def test_generating_lot_line_vals_without_a_product_is_an_error():
    """``:1133-1134`` — «No product found to generate Serials/Lots for»."""
    with pytest.raises(UserError):
        StockMove.action_generate_lot_line_vals({}, 'generate', 'SN-001', 2, '')


def test_generating_lot_line_vals_rejects_an_unknown_mode(serial_variant):
    """``:1135`` — ``assert mode in ('generate', 'import')``."""
    with pytest.raises(AssertionError):
        StockMove.action_generate_lot_line_vals(
            {'default_product_id': serial_variant.pk, 'default_tracking': 'serial'},
            'inventar', 'SN-001', 1, '')


def test_generating_lot_line_vals_produces_one_row_per_serial(
        serial_variant, destination, company):
    """``:1160-1161`` — modo ``generate`` con serie: una fila por unidad."""
    salida = StockMove.action_generate_lot_line_vals(
        {'default_product_id': serial_variant.pk,
         'default_tracking': 'serial',
         'default_company_id': company.pk,
         'default_location_dest_id': destination.pk},
        'generate', 'SN-001', 3, '')

    assert [v['lot_name'] for v in salida] == ['SN-001', 'SN-002', 'SN-003']


def test_importing_lot_line_vals_reads_the_pasted_text(
        serial_variant, destination, company):
    """``:1163-1165`` — modo ``import``: los nombres salen del texto pegado."""
    salida = StockMove.action_generate_lot_line_vals(
        {'default_product_id': serial_variant.pk,
         'default_tracking': 'serial',
         'default_company_id': company.pk,
         'default_location_dest_id': destination.pk},
        'import', '', 0, 'SN-A\nSN-B')

    assert [v['lot_name'] for v in salida] == ['SN-A', 'SN-B']


def test_a_lot_tracked_product_splits_the_quantity_across_lots(
        plain_variant, destination, company, unit):
    """``:1141-1149`` — con seguimiento por lote, la demanda se reparte."""
    plain_variant.product_tmpl.tracking = 'lot'
    plain_variant.product_tmpl.save()

    salida = StockMove.action_generate_lot_line_vals(
        {'default_product_id': plain_variant.pk,
         'default_tracking': 'lot',
         'default_quantity': 7,
         'default_company_id': company.pk,
         'default_location_dest_id': destination.pk},
        'generate', 'LOT-001', 3, '')

    assert [v['quantity'] for v in salida] == [3, 3, 1]


def test_a_non_positive_quantity_per_lot_is_an_error(
        plain_variant, destination, company):
    """``:1140-1141`` — «should always be a positive value»."""
    with pytest.raises(UserError):
        StockMove.action_generate_lot_line_vals(
            {'default_product_id': plain_variant.pk,
             'default_tracking': 'lot',
             'default_quantity': 7,
             'default_company_id': company.pk,
             'default_location_dest_id': destination.pk},
            'generate', 'LOT-001', 0, '')
