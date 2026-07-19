"""Contrato de ``IrLogging`` (``ir.logging``) — portación fiel de Odoo,
DEC-08 slice 2 de ``adoptar-arquitectura-server-service-odoo``.

Reemplaza a ``core.AppLog`` (ver ``addons/base/models/ir_logging_log.py`` para
el mapeo de campos completo). Verifica:

- importable desde el hogar canónico ``addons.base.models``,
- append-only (hereda ``AppendOnlyModel``, SOL-011/DEC-LOG-05),
- ``db_table`` fiel a Odoo (``ir_logging``),
- el ``DatabaseLogHandler`` (``core.logging_handlers``) escribe en este
  modelo, no en el ``AppLog`` previo.

El contrato append-only detallado (INSERT permitido / UPDATE-DELETE de
instancia bloqueados / bulk permitido) para ``RequestLog`` vive en
``tests/unit/core/test_log_immutability.py``; aquí se cubre el mismo contrato
para ``IrLogging``.

Toca DB → django_db.
"""
import logging

import pytest

from addons.base.models import AppendOnlyModel, IrLogging
from core.logging_context import clear_correlation_id
from core.logging_handlers import DatabaseLogHandler

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _make_ir_logging():
    return IrLogging.objects.create(
        name='apps.x', level=IrLogging.LEVEL_INFO, message='hola')


# --- Importable desde el hogar canónico ------------------------------------

def test_importable_desde_addons_base_models():
    assert IrLogging.__module__ == 'addons.base.models.ir_logging_log'


# --- db_table fiel a Odoo ---------------------------------------------------

def test_db_table_fiel_a_odoo():
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
