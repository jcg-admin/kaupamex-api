"""Tests — addon ``product_expiry`` (caducidad + FEFO).

Reescritos en el mismo pase que :ref:`h-api-576`: el addon dejó de inventar
``ProductExpiryConfig``/``StockLotExpiry`` —dos modelos que la referencia no
tiene— y ahora extiende ``product.template``, ``stock.lot``, ``stock.quant`` y
``stock.move``, como ``odoo19c: product_expiry/models/*``. Los tests ejercitan
esa forma.

Cubre: la delegación template→variante de los cinco campos de configuración, el
cálculo de las fechas del lote en sus **dos** ramas (creación y desplazamiento),
la alerta de caducidad alcanzada, el ``display_name`` con fecha, la estrategia
FEFO sobre ``gather``, el descuento de lo caducado en ``available_qty``, y el
barrido ``alert_date_exceeded``.
"""
import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.product_expiry.models import production_lot as pe_lot
from addons.product_expiry.models import res_config_settings as pe_config
from addons.product_expiry.models import stock_move_line as pe_move_line
from addons.product_expiry.models import stock_picking as pe_picking
from addons.product_expiry.models import stock_rule as pe_rule
from addons.stock.models import ProductRemoval, StockLocation, StockLot, StockQuant
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.integration

_slug_seq = [0]


def _product(expiration=30, use=20, removal=25, alert=15, tracked=True):
    """Producto con la configuración de caducidad puesta en su **template**.

    Es donde la referencia la declara (``odoo19c: product_product.py:20-34``);
    la variante la expone por delegación, y eso es justo lo que el primer test
    verifica.
    """
    _slug_seq[0] += 1
    n = _slug_seq[0]
    producto = make_product(
        name=f'Exp Prod {n}', default_code=f'EXP-{n:04d}', price=Decimal('100.00'),
    )
    plantilla = producto.product_tmpl
    plantilla.tracking = 'lot' if tracked else 'none'
    plantilla.use_expiration_date = tracked
    plantilla.expiration_time = expiration
    plantilla.use_time = use
    plantilla.removal_time = removal
    plantilla.alert_time = alert
    plantilla.save()
    producto.refresh_from_db()
    return producto


def _internal(name='WH/Stock'):
    return StockLocation.objects.create(name=name, usage=StockLocation.USAGE_INTERNAL)


# -- delegación template → variante -----------------------------------------


def test_variant_delegates_the_five_config_fields_to_its_template(db):
    """Los cinco campos viven en el template; la variante los lee (≙ _inherits)."""
    producto = _product(expiration=30, use=20, removal=25, alert=15)
    assert producto.use_expiration_date is True
    assert producto.expiration_time == 30
    assert producto.use_time == 20
    assert producto.removal_time == 25
    assert producto.alert_time == 15


def test_untracked_product_cannot_use_expiration_dates(db):
    """≙ ``ProductTemplate.write`` — sin trazabilidad no hay lote que fechar."""
    producto = _product()
    plantilla = producto.product_tmpl
    plantilla.tracking = 'none'
    plantilla.use_expiration_date = True
    plantilla.save()
    plantilla.refresh_from_db()
    assert plantilla.use_expiration_date is False


# -- las cuatro fechas del lote ---------------------------------------------


def test_expiration_date_is_derived_from_the_product_lead(db):
    """≙ ``_compute_expiration_date``: ahora + ``expiration_time`` días."""
    lote = StockLot.objects.create(name='L1', product=_product(expiration=30))
    lote.compute_expiration_date()
    delta = lote.expiration_date - timezone.now()
    assert datetime.timedelta(days=29, hours=23) < delta <= datetime.timedelta(days=30)


def test_expiration_date_already_set_is_respected(db):
    """La referencia sólo fija la caducidad ``if not lot.expiration_date``."""
    lote = StockLot.objects.create(name='L2', product=_product(expiration=30))
    fijada = timezone.now() + datetime.timedelta(days=7)
    lote.expiration_date = fijada
    lote.compute_expiration_date()
    assert lote.expiration_date == fijada


def test_untracked_product_derives_no_dates(db):
    """Sin ``use_expiration_date`` no hay nada que derivar."""
    lote = StockLot.objects.create(name='L3', product=_product(tracked=False))
    lote.compute_expiration_date()
    lote.compute_dates()
    assert lote.expiration_date is None
    assert lote.removal_date is None


def test_the_three_derived_dates_subtract_their_own_lead(db):
    """≙ la rama de creación de ``_compute_dates``."""
    lote = StockLot.objects.create(
        name='L4', product=_product(expiration=30, use=20, removal=25, alert=15))
    lote.compute_expiration_date()
    lote.compute_dates()
    assert lote.use_date == lote.expiration_date - datetime.timedelta(days=20)
    assert lote.removal_date == lote.expiration_date - datetime.timedelta(days=25)
    assert lote.alert_date == lote.expiration_date - datetime.timedelta(days=15)


def test_moving_the_expiration_shifts_the_others_by_the_same_delta(db):
    """≙ la rama ``elif`` de ``_compute_dates``, la que preserva el ajuste manual.

    Es la mitad que un porte apresurado pierde: al **editar** la caducidad de un
    lote existente las otras tres se desplazan, no se recalculan — si se
    recalcularan, cualquier ajuste manual del usuario se perdería.
    """
    lote = StockLot.objects.create(
        name='L5', product=_product(expiration=30, use=20, removal=25, alert=15))
    lote.compute_expiration_date()
    lote.compute_dates()
    anterior = lote.expiration_date
    # El usuario mueve a mano la fecha de retiro, y luego la caducidad.
    lote.removal_date = anterior - datetime.timedelta(days=3)
    lote.expiration_date = anterior + datetime.timedelta(days=10)
    lote.compute_dates(previous_expiration=anterior)

    assert lote.removal_date == anterior - datetime.timedelta(days=3) \
        + datetime.timedelta(days=10)          # el ajuste manual sobrevive
    assert lote.use_date == anterior - datetime.timedelta(days=20) \
        + datetime.timedelta(days=10)
    assert lote.alert_date == anterior - datetime.timedelta(days=15) \
        + datetime.timedelta(days=10)


def test_expiry_alert_flips_when_the_expiration_is_reached(db):
    """≙ ``_compute_product_expiry_alert``."""
    producto = _product()
    vencido = StockLot.objects.create(
        name='L6', product=producto,
        expiration_date=timezone.now() - datetime.timedelta(days=1))
    vigente = StockLot.objects.create(
        name='L7', product=producto,
        expiration_date=timezone.now() + datetime.timedelta(days=1))
    sin_fecha = StockLot.objects.create(name='L8', product=producto)
    assert vencido.product_expiry_alert is True
    assert vigente.product_expiry_alert is False
    assert sin_fecha.product_expiry_alert is False


def test_display_name_carries_the_expiration_and_relays_without_it(db):
    """≙ ``_compute_display_name``: el formato cuando caduca, el relevo si no."""
    producto = _product()
    caduca = StockLot.objects.create(
        name='L9', product=producto,
        expiration_date=timezone.now() + datetime.timedelta(days=5))
    fecha = caduca.expiration_date.date()
    assert caduca.display_name() == f'L9\t--{fecha}--'
    # Sin caducidad, la función devuelve None y `chain_method` releva a la base.
    assert StockLot.objects.create(name='L10', product=producto).display_name() == 'L10'


# -- FEFO y disponibilidad ---------------------------------------------------


def test_fefo_orders_by_removal_date_not_by_entry(db):
    """≙ ``_get_removal_strategy_order``: el que se retira antes sale antes.

    El lote que ENTRÓ después es el que se retira primero — así el test
    distingue FEFO de FIFO en vez de dejar que coincidan por casualidad.
    """
    producto, ubicacion = _product(), _internal()
    viejo = StockLot.objects.create(
        name='LA', product=producto,
        removal_date=timezone.now() + datetime.timedelta(days=30))
    urgente = StockLot.objects.create(
        name='LB', product=producto,
        removal_date=timezone.now() + datetime.timedelta(days=2))
    StockQuant.objects.create(
        product=producto, location=ubicacion, lot=viejo, quantity=Decimal('5.00'),
        in_date=timezone.now() - datetime.timedelta(days=10))
    StockQuant.objects.create(
        product=producto, location=ubicacion, lot=urgente, quantity=Decimal('5.00'),
        in_date=timezone.now())

    # FEFO se declara en la ubicación, como en la referencia: ``_gather`` la
    # deriva con ``_get_removal_strategy``, no la recibe por argumento.
    ubicacion.removal_strategy = ProductRemoval.objects.create(
        name='FEFO', method='fefo')
    ubicacion.save(update_fields=['removal_strategy', 'updated_at'])
    assert StockQuant._get_removal_strategy(producto, ubicacion) == 'fefo'
    fefo = list(StockQuant._gather(producto, ubicacion))
    assert [q.lot.name for q in fefo] == ['LB', 'LA']

    # La estrategia de la base sigue respondiendo: es un relevo, no un pisotón.
    # El satélite encadena ``_get_removal_strategy_order``, así que ``fifo``
    # cae al método de ``stock`` intacto.
    assert StockQuant._get_removal_strategy_order('fifo') == ('in_date', 'id')
    ubicacion.removal_strategy = None
    ubicacion.save(update_fields=['removal_strategy', 'updated_at'])
    fifo = list(StockQuant._gather(producto, ubicacion))
    assert [q.lot.name for q in fifo] == ['LA', 'LB']


def test_expired_stock_stops_counting_as_available(db):
    """≙ ``_compute_available_quantity``: lo retirable no está disponible."""
    producto, ubicacion = _product(), _internal()
    vencido = StockLot.objects.create(
        name='LC', product=producto,
        removal_date=timezone.now() - datetime.timedelta(days=1))
    fresco = StockLot.objects.create(
        name='LD', product=producto,
        removal_date=timezone.now() + datetime.timedelta(days=10))
    StockQuant.objects.create(
        product=producto, location=ubicacion, lot=vencido, quantity=Decimal('4.00'))
    StockQuant.objects.create(
        product=producto, location=ubicacion, lot=fresco, quantity=Decimal('6.00'))

    assert StockQuant.available_qty(producto, ubicacion) == Decimal('6.00')


def test_available_qty_never_goes_negative(db):
    """La referencia acota en cero; no invierte el signo."""
    producto, ubicacion = _product(), _internal()
    vencido = StockLot.objects.create(
        name='LE', product=producto,
        removal_date=timezone.now() - datetime.timedelta(days=1))
    StockQuant.objects.create(
        product=producto, location=ubicacion, lot=vencido,
        quantity=Decimal('4.00'), reserved_quantity=Decimal('0.00'))
    # Reservar todo deja la base en 0; el descuento no debe hundirla.
    assert StockQuant.available_qty(producto, ubicacion) >= Decimal('0.00')


# -- el barrido de alertas ---------------------------------------------------


def test_alert_sweep_marks_only_lots_with_internal_stock(db):
    """≙ ``_alert_date_exceeded``: la intersección con la existencia interna.

    Un lote vencido pero agotado NO genera aviso — es el paso que separa este
    barrido de un simple filtro por fecha.
    """
    producto, ubicacion = _product(), _internal()
    ayer = timezone.now() - datetime.timedelta(days=1)
    con_stock = StockLot.objects.create(name='LF', product=producto, alert_date=ayer)
    agotado = StockLot.objects.create(name='LG', product=producto, alert_date=ayer)
    futuro = StockLot.objects.create(
        name='LH', product=producto,
        alert_date=timezone.now() + datetime.timedelta(days=5))
    StockQuant.objects.create(
        product=producto, location=ubicacion, lot=con_stock, quantity=Decimal('2.00'))
    StockQuant.objects.create(
        product=producto, location=ubicacion, lot=agotado, quantity=Decimal('0.00'))

    marcados = StockLot.alert_date_exceeded()

    assert [lote.name for lote in marcados] == ['LF']
    con_stock.refresh_from_db()
    agotado.refresh_from_db()
    futuro.refresh_from_db()
    assert con_stock.product_expiry_reminded is True
    assert agotado.product_expiry_reminded is False
    assert futuro.product_expiry_reminded is False


def test_alert_sweep_is_idempotent(db):
    """``product_expiry_reminded`` existe para no avisar dos veces."""
    producto, ubicacion = _product(), _internal()
    lote = StockLot.objects.create(
        name='LI', product=producto,
        alert_date=timezone.now() - datetime.timedelta(days=1))
    StockQuant.objects.create(
        product=producto, location=ubicacion, lot=lote, quantity=Decimal('3.00'))

    assert len(StockLot.alert_date_exceeded()) == 1
    assert StockLot.alert_date_exceeded() == []


def test_scheduler_task_delegates_to_the_lot_sweep(db):
    """≙ la línea de ``_run_scheduler_tasks`` que este addon aporta."""
    producto, ubicacion = _product(), _internal()
    lote = StockLot.objects.create(
        name='LJ', product=producto,
        alert_date=timezone.now() - datetime.timedelta(days=1))
    StockQuant.objects.create(
        product=producto, location=ubicacion, lot=lote, quantity=Decimal('1.00'))

    assert [x.name for x in pe_rule.run_expiry_alert_task()] == ['LJ']


def test_the_four_blocked_modules_expose_a_declared_no_op():
    """Los cuatro archivos sin destino portado son no-op, no ausencias.

    ``apps.py`` los recorre en ``_EXTENSIONES``: si alguno dejara de exponer
    ``apply_product_expiry_extensions``, el arranque reventaría. El test fija
    ese contrato — y de paso deja constancia de que la ausencia es declarada,
    no un olvido (cada docstring nombra su causa y su tarea sucesora).
    """
    for modulo in (pe_config, pe_move_line, pe_picking, pe_rule):
        assert modulo.apply_product_expiry_extensions() is None


def test_lot_dates_survive_a_round_trip_to_the_database(db):
    """Las cuatro fechas son COLUMNAS de ``stock.lot``, no properties.

    Es la diferencia que :ref:`h-api-576` corrige: antes vivían en un modelo
    satélite inventado. Si la migración no aterrizó, este test falla al leer.
    """
    lote = StockLot.objects.create(
        name='LK', product=_product(expiration=10, use=3, removal=5, alert=2))
    lote.compute_expiration_date()
    lote.compute_dates()
    lote.save(update_fields=[
        'expiration_date', 'use_date', 'removal_date', 'alert_date', 'updated_at'])

    releido = StockLot.objects.get(pk=lote.pk)
    assert releido.expiration_date == lote.expiration_date
    assert releido.removal_date == lote.removal_date
    assert releido.use_date == lote.use_date
    assert releido.alert_date == lote.alert_date
    assert pe_lot.use_expiration_date(releido) is True
