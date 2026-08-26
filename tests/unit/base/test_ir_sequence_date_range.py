"""``ir.sequence`` / ``ir.sequence.date_range`` — el contrato de numeración.

Porta ``odoo19c: odoo/addons/base/models/ir_sequence.py`` (LGPL-3). Ejercita
las piezas que el porte anterior no tenia, y las mide **contra el motor real**:
las secuencias nativas de PostgreSQL 16 existen y se consultan en
``pg_sequences``, no se simulan.

El control que puede fallar — MEDIDO, no supuesto
--------------------------------------------------

Dos guardas del porte, cada una anulada y vuelta a correr:

1. **El candado de ``no_gap``.** Retirando ``FOR UPDATE NOWAIT`` de
   ``_update_nogap``, la suite pasa de **18 passed** a **17 passed y el 18º
   colgado indefinidamente**: sin ``NOWAIT``, el ``SELECT … FOR UPDATE`` de la
   fila ya tomada **espera** en vez de fallar. El resultado discrimina —de
   forma incómoda, porque cuelga en vez de fallar— y por eso se anota aquí en
   lugar de dejarlo al descubrimiento de quien lo rompa.

   La version anterior de ese caso NO discriminaba: emitia el
   ``select … for update nowait`` **por su cuenta**, asi que media PostgreSQL y
   no el porte, y seguia verde con el candado retirado del codigo. Sub-patron D
   de ``metrica-decide-la-conclusion.md``.

2. **La guarda de paso cero.** ``test_a_zero_step_is_refused`` fallo en la
   primera corrida —``DID NOT RAISE``— y el defecto estaba en el CODIGO, no en
   el caso: ``save()`` pasaba ``self.number_increment or 1``, y ese ``or`` se
   tragaba el cero antes de que ``_create_sequence`` pudiera rechazarlo. La
   fuente escribe ``vals.get('number_increment', 1)``, cuyo default aplica solo
   si la clave falta. Un ``or`` defensivo que neutraliza una guarda es el mismo
   sub-patron D, esta vez en produccion.

3. **La secuencia nativa** — si ``standard`` volviera a llevar el contador en
   la fila, ``_predict_nextval`` no tendria de donde leer y
   ``test_standard_uses_a_native_sequence`` cae con ``UndefinedTable``.
"""
from datetime import date, timedelta

import pytest
from django.db import connection, transaction
from django.db.utils import (IntegrityError, OperationalError,
                             ProgrammingError)

from addons.base.models.res_company import ResCompany
from addons.base.models.ir_sequence import (
    IrSequence,
    IrSequenceDateRange,
    _predict_nextval,
    _select_nextval,
)
from exceptions import UserError


@pytest.fixture
def standard(db):
    return IrSequence.objects.create(
        name='Factura', code='factura', implementation='standard',
        prefix='F/%(year)s/', padding=4)


@pytest.fixture
def no_gap(db):
    return IrSequence.objects.create(
        name='Folio fiscal', code='folio', implementation='no_gap',
        prefix='FF-', padding=5)


# --------------------------------------------------------------------------
# La secuencia nativa — lo que la divergencia retirada decia que no aplicaba
# --------------------------------------------------------------------------

def test_standard_uses_a_native_sequence(standard):
    """La fila NO lleva el contador: lo lleva PostgreSQL."""
    with connection.cursor() as cursor:
        cursor.execute(
            "select count(*) from pg_sequences where sequencename = %s",
            ['ir_sequence_%03d' % standard.pk])
        assert cursor.fetchone()[0] == 1


def test_predict_does_not_consume(standard):
    """``_predict_nextval`` mira sin gastar — el punto de que exista."""
    antes = _predict_nextval('%03d' % standard.pk)
    otra_vez = _predict_nextval('%03d' % standard.pk)
    assert antes == otra_vez
    consumido = _select_nextval('ir_sequence_%03d' % standard.pk)
    assert consumido == antes
    assert _predict_nextval('%03d' % standard.pk) == antes + 1


def test_number_next_actual_reads_the_engine(standard):
    assert standard.number_next_actual == 1
    standard._next()
    assert standard.number_next_actual == 2


def test_dropping_the_row_drops_the_sequence(standard):
    seq_name = 'ir_sequence_%03d' % standard.pk
    standard.delete()
    with connection.cursor() as cursor:
        cursor.execute(
            "select count(*) from pg_sequences where sequencename = %s",
            [seq_name])
        assert cursor.fetchone()[0] == 0


def test_a_zero_step_is_refused(db):
    """≙ la guarda de ``_create_sequence``: *"Step must not be zero."*"""
    with pytest.raises(UserError):
        IrSequence.objects.create(
            name='Rota', code='rota', number_increment=0)


# --------------------------------------------------------------------------
# no_gap — el contador en la fila, y su candado
# --------------------------------------------------------------------------

def test_no_gap_has_no_native_sequence(no_gap):
    with connection.cursor() as cursor:
        cursor.execute(
            "select count(*) from pg_sequences where sequencename = %s",
            ['ir_sequence_%03d' % no_gap.pk])
        assert cursor.fetchone()[0] == 0


def test_no_gap_increments_the_row(no_gap):
    primero = no_gap._next()
    segundo = no_gap._next()
    assert primero == 'FF-00001'
    assert segundo == 'FF-00002'
    no_gap.refresh_from_db()
    assert no_gap.number_next == 3


@pytest.mark.django_db(transaction=True)
def test_the_lock_refuses_a_second_reader():
    """``FOR UPDATE NOWAIT``: el segundo lector **falla**, no espera.

    Ejerce NUESTRO camino —``next_by_id`` → ``_update_nogap``— con la fila ya
    tomada por otra conexion. La version anterior de este caso emitia el
    ``select ... for update nowait`` **por su cuenta**: media PostgreSQL, no el
    porte, y seguia verde con el candado retirado del codigo. Es el sub-patron
    D de ``metrica-decide-la-conclusion.md``.
    """
    seq = IrSequence.objects.create(
        name='Con candado', code='candado', implementation='no_gap')
    tabla = connection.ops.quote_name(seq._meta.db_table)
    otra = connection.copy()
    otra.connect()
    try:
        with otra.cursor() as tenedor:
            tenedor.execute('begin')
            tenedor.execute(
                f'select number_next from {tabla} where id = %s '
                f'for update nowait', [seq.pk])
            # La fila esta tomada: el consumo del folio debe FALLAR, no esperar.
            with pytest.raises((OperationalError, ProgrammingError)):
                seq.next_by_id()
            tenedor.execute('rollback')
    finally:
        otra.close()
    seq.delete()


# --------------------------------------------------------------------------
# El rango de fecha — lo que hace que el folio reinicie por ejercicio
# --------------------------------------------------------------------------

def test_the_range_is_created_on_demand(standard):
    standard.use_date_range = True
    standard.save()
    assert standard.date_range_ids.count() == 0
    standard._next()
    assert standard.date_range_ids.count() == 1
    rango = standard.date_range_ids.first()
    hoy = date.today()
    assert rango.date_from == date(hoy.year, 1, 1)
    assert rango.date_to == date(hoy.year, 12, 31)


def test_the_range_has_its_own_native_sequence(standard):
    standard.use_date_range = True
    standard.save()
    standard._next()
    rango = standard.date_range_ids.first()
    with connection.cursor() as cursor:
        cursor.execute(
            "select count(*) from pg_sequences where sequencename = %s",
            ['ir_sequence_%03d_%03d' % (standard.pk, rango.pk)])
        assert cursor.fetchone()[0] == 1


def test_two_ranges_number_apart(standard):
    """El punto entero de la subsecuencia: cada ejercicio empieza en uno."""
    standard.use_date_range = True
    standard.save()
    anterior = IrSequenceDateRange.objects.create(
        sequence=standard, date_from=date(2025, 1, 1), date_to=date(2025, 12, 31))
    actual = IrSequenceDateRange.objects.create(
        sequence=standard, date_from=date(2026, 1, 1), date_to=date(2026, 12, 31))
    assert standard._next(sequence_date=date(2025, 6, 1)).endswith('0001')
    assert standard._next(sequence_date=date(2025, 6, 2)).endswith('0002')
    assert standard._next(sequence_date=date(2026, 6, 1)).endswith('0001')
    assert anterior.number_next_actual == 3
    assert actual.number_next_actual == 2


def test_a_new_range_is_trimmed_by_its_neighbour(standard):
    """≙ el recorte de ``_create_date_range_seq``: los rangos no se solapan."""
    standard.use_date_range = True
    standard.save()
    hoy = date.today()
    later_from = date(hoy.year, 7, 1)
    if hoy >= later_from:
        later_from = hoy + timedelta(days=1)
    IrSequenceDateRange.objects.create(
        sequence=standard, date_from=later_from,
        date_to=date(hoy.year, 12, 31))
    nuevo = standard._create_date_range_seq(hoy)
    assert nuevo.date_to == later_from - timedelta(days=1)


def test_two_identical_ranges_are_refused(standard):
    """≙ ``_unique_range_per_sequence``, con su nombre conservado."""
    IrSequenceDateRange.objects.create(
        sequence=standard, date_from=date(2026, 1, 1), date_to=date(2026, 12, 31))
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            IrSequenceDateRange.objects.create(
                sequence=standard, date_from=date(2026, 1, 1),
                date_to=date(2026, 12, 31))


# --------------------------------------------------------------------------
# Interpolacion — los quince tokens, no siete
# --------------------------------------------------------------------------

def test_the_fifteen_tokens_resolve(db):
    seq = IrSequence.objects.create(
        name='Todos', code='todos',
        prefix='%(year)s%(month)s%(day)s%(y)s%(doy)s%(woy)s%(weekday)s'
               '%(h24)s%(h12)s%(min)s%(sec)s%(isoyear)s%(isoy)s%(isoweek)s/',
        padding=1)
    salida = seq._next()
    assert salida.endswith('/1')


def test_the_range_and_current_forms_resolve(db):
    """Cada token tiene tres formas; la version anterior portaba una."""
    seq = IrSequence.objects.create(
        name='Formas', code='formas',
        prefix='%(range_year)s-%(current_year)s-%(year)s/', padding=2)
    assert seq._next().endswith('/01')


def test_a_bad_token_is_refused(db):
    seq = IrSequence.objects.create(
        name='Mala', code='mala', prefix='%(no_existe)s/')
    with pytest.raises(UserError):
        seq._next()


def test_next_by_code_prefers_the_company_sequence(db):
    company = ResCompany.objects.create(name='L1 de prueba')
    IrSequence.objects.create(name='Global', code='compartido', prefix='G-')
    IrSequence.objects.create(name='De company', code='compartido',
                              prefix='E-', company=company)
    assert IrSequence.next_by_code('compartido', company=company).startswith('E-')
    assert IrSequence.next_by_code('compartido').startswith('G-')


def test_next_by_code_without_a_sequence_is_none(db):
    assert IrSequence.next_by_code('no-existe') is None
