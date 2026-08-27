"""Contrato de ``IrLogging`` (``ir.logging``) — portación fiel de Odoo,
DEC-08 slice 2 de ``adoptar-arquitectura-server-service-odoo``.

Reemplaza a ``core.AppLog`` (ver ``addons/base/models/ir_logging.py`` para
el mapeo de campos completo). Verifica:

- importable desde el hogar canónico ``addons.base.models``,
- append-only (hereda ``AppendOnlyModel``, SOL-011/DEC-LOG-05),
- ``db_table`` fiel a Odoo (``ir_logging``),
- el ``DatabaseLogHandler`` (``tools.logging_handlers``) escribe en este
  modelo, no en el ``AppLog`` previo.

El contrato append-only detallado (INSERT permitido / UPDATE-DELETE de
instancia bloqueados / bulk permitido) se cubre aquí. Tenía un gemelo para
``RequestLog`` en ``tests/unit/core/test_log_immutability.py``, retirado con
el modelo (DEC-AF-11).

Toca DB → django_db.
"""
import logging
from datetime import timedelta

import pytest
from django.utils import timezone

from addons.base import exception_handling
from addons.base.models import AppendOnlyModel, IrLogging
from tools.logging_context import clear_correlation_id
from tools.logging_handlers import DatabaseLogHandler

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _make_ir_logging():
    return IrLogging.objects.create(
        name='apps.x', level=IrLogging.LEVEL_INFO, message='hola')


# --- Importable desde el hogar canónico ------------------------------------

def test_importable_desde_addons_base_models():
    assert IrLogging.__module__ == 'addons.base.models.ir_logging'


# --- db_table fiel a Odoo ---------------------------------------------------

def test_db_table_matches_reference():
    assert IrLogging._meta.db_table == 'ir_logging'
    assert IrLogging._meta.app_label == 'base'


def test_hereda_append_only_model():
    assert issubclass(IrLogging, AppendOnlyModel)


# --- Campos fieles a Odoo (nombre + tipo/level con divergencias) -----------

def test_campos_faithful_presentes():
    field_names = {f.name for f in IrLogging._meta.get_fields()}
    for expected in ('name', 'type', 'dbname', 'level', 'message', 'path',
                     'func', 'line'):
        assert expected in field_names, f'falta el campo Odoo {expected!r}'
    # Columnas propias (no-Odoo, DEC-LOG-07):
    for extra in ('correlation_id', 'trace'):
        assert extra in field_names, f'falta la columna propia {extra!r}'


def test_type_default_server():
    row = _make_ir_logging()
    assert row.type == IrLogging.TYPE_SERVER


# --- Append-only (INSERT permitido / UPDATE-DELETE de instancia bloqueado) -

def test_insert_allowed():
    row = _make_ir_logging()
    assert row.pk is not None
    assert IrLogging.objects.filter(pk=row.pk).exists()


def test_update_de_instancia_bloqueado():
    row = _make_ir_logging()
    row.message = 'modificado'
    with pytest.raises(PermissionError):
        row.save()
    assert IrLogging.objects.get(pk=row.pk).message == 'hola'


def test_delete_de_instancia_bloqueado():
    row = _make_ir_logging()
    with pytest.raises(PermissionError):
        row.delete()
    assert IrLogging.objects.filter(pk=row.pk).exists()


def test_bulk_delete_permitido():
    row = _make_ir_logging()
    deleted, _ = IrLogging.objects.filter(pk=row.pk).delete()
    assert deleted == 1
    assert not IrLogging.objects.filter(pk=row.pk).exists()


# --- El log handler escribe en IrLogging (no en el AppLog previo) ----------

@pytest.fixture
def logger():
    lg = logging.getLogger('test.ir_logging')
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    handler = DatabaseLogHandler()
    lg.addHandler(handler)
    yield lg
    lg.removeHandler(handler)
    clear_correlation_id()


def test_database_log_handler_escribe_en_ir_logging(logger):
    logger.info('hello from ir.logging')
    row = IrLogging.objects.get()
    assert row.name == 'test.ir_logging'
    assert row.level == 'INFO'
    assert row.message == 'hello from ir.logging'
    assert row.type == IrLogging.TYPE_SERVER


def test_database_log_handler_puebla_call_site(logger):
    """Divergencia positiva respecto a AppLog: path/func/line poblados desde
    el LogRecord (Odoo los declara required; el AppLog previo no los tenía)."""
    logger.info('con call site')
    row = IrLogging.objects.get()
    assert row.path  # LogRecord.pathname del propio test
    assert row.func  # LogRecord.funcName
    assert row.line and row.line != '0'


# --- Retención: la tercera ventana, la del 4xx (tarea #616) ----------------
#
# DEC-LOG-05 dio 30 días al 4xx cuando vivía en ``RequestLog``. DEC-AF-11
# retiró ese modelo y el 4xx pasó a ser un ``WARNING`` de ``ir.logging``, que
# se conserva 90. Estos casos fijan que la ventana volvió a 30 **sin** tocar
# la de los demás WARNING.

def _age(pk, days):
    IrLogging.objects.filter(pk=pk).update(
        created_at=timezone.now() - timedelta(days=days))


def _make(name, level, days):
    row = IrLogging.objects.create(name=name, level=level, message='x')
    _age(row.pk, days)
    return row


def test_the_4xx_is_purged_at_30_days():
    row = _make('django.request', IrLogging.LEVEL_WARNING, 31)
    IrLogging._purge_expired()
    assert not IrLogging.objects.filter(pk=row.pk).exists()


def test_the_4xx_survives_before_30_days():
    row = _make('django.request', IrLogging.LEVEL_WARNING, 29)
    IrLogging._purge_expired()
    assert IrLogging.objects.filter(pk=row.pk).exists()


def test_a_warning_that_is_not_4xx_keeps_its_90_days():
    """El caso que separa las dos ventanas: mismo nivel, otro logger."""
    row = _make('addons.sale.services', IrLogging.LEVEL_WARNING, 31)
    IrLogging._purge_expired()
    assert IrLogging.objects.filter(pk=row.pk).exists()
    _age(row.pk, 91)
    IrLogging._purge_expired()
    assert not IrLogging.objects.filter(pk=row.pk).exists()


def test_a_django_request_error_stays_out_of_the_4xx_window():
    """Un 5xx emite ERROR por el mismo logger: la clase alta lo conserva."""
    row = _make('django.request', IrLogging.LEVEL_ERROR, 31)
    IrLogging._purge_expired()
    assert IrLogging.objects.filter(pk=row.pk).exists()


def test_the_three_sets_are_disjoint_in_the_count():
    """Un 4xx de más de 90 días se cuenta UNA vez, no dos.

    Sin el ``.exclude(cuatro_xx)`` del conjunto alto, el ``dry_run`` —cuyo
    único trabajo es decir cuántas filas caerían— publicaría 2 por 1 fila.
    """
    _make('django.request', IrLogging.LEVEL_WARNING, 100)
    conteos = IrLogging._purge_expired(dry_run=True)
    assert conteos['IrLogging 4xx'] == 1
    assert conteos['IrLogging WARNING/ERROR'] == 0
    assert IrLogging.objects.count() == 1   # dry_run no borra


def test_the_4xx_discriminator_is_still_exact():
    """Vigila la premisa: WARNING sobre ``django.request`` implica 4xx.

    La medición está en el bloque ``_ACCESS_LOGGER`` del modelo: en Django
    6.0.5 los emisores de ese canal son ``log_response`` (4xx→WARNING,
    5xx→ERROR), el ``UnicodeDecodeError`` de ASGI (status_code=400) y dos
    ``logger.debug`` de los handlers. Un quinto emisor a WARNING metería su
    fila en la ventana de 30 días **en silencio**.

    Este caso no puede detectar ese quinto emisor —no hay forma sintáctica de
    hacerlo— pero sí fija el nombre del canal, que es de dónde cuelga toda la
    política. Si alguien lo renombra, esto falla en vez de purgar mal.
    """
    assert IrLogging._ACCESS_LOGGER == 'django.request'
    assert IrLogging.ACCESS_LEVEL_DAYS == 30
    assert IrLogging.HIGH_LEVEL_DAYS == 90
    # El logger que nuestro propio handler usa, leído del módulo que emite.
    assert exception_handling._logger.name == IrLogging._ACCESS_LOGGER
