"""Tests unitarios — DatabaseLogHandler (SOL-011 T-03, DEC-LOG-02).

Se prueba el handler **directamente** (testing.py sobreescribe LOGGING con
NullHandler, asi que no corre via config durante la suite). Verifican que:
  - persiste cada record a IrLogging (name, level, message),
  - redacta secretos Nivel 1 en message y trace (DEC-LOG-03),
  - captura el traceback cuando hay exc_info,
  - sella el correlation_id del contexto (DEC-LOG-07), vacio fuera de request,
  - es anti-recursion: ignora records de django.db* (DEC-LOG-04),
  - es no bloqueante: un fallo del insert no propaga (DEC-LOG-04).

``IrLogging`` (``ir.logging``, ``addons.base``) reemplaza a ``core.AppLog``
desde DEC-08 slice 2 — mismo comportamiento del handler, otro modelo destino.

Toca DB (IrLogging) → django_db.
"""
import logging
from unittest import mock

import pytest

from addons.base.models import IrLogging
from tools.logging_context import clear_correlation_id, set_correlation_id
from tools.logging_handlers import DatabaseLogHandler

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def logger():
    lg = logging.getLogger('test.applog')
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    handler = DatabaseLogHandler()
    lg.addHandler(handler)
    yield lg
    lg.removeHandler(handler)
    clear_correlation_id()


def test_persists_record_to_applog(logger):
    logger.info('hello world')
    row = IrLogging.objects.get()
    assert row.name == 'test.applog'
    assert row.level == 'INFO'
    assert row.message == 'hello world'


def test_scrubs_secret_in_msg(logger):
    logger.warning('login attempt password=hunter2')
    row = IrLogging.objects.get()
    assert 'hunter2' not in row.message
    assert row.level == 'WARNING'


def test_captures_and_scrubs_traceback(logger):
    try:
        secret_token = 'tok_live_51H'  # noqa: F841 — aparece en locals de la traza
        raise ValueError(f'boom with card_token={secret_token}')
    except ValueError:
        logger.error('charge failed', exc_info=True)
    row = IrLogging.objects.get()
    assert row.trace  # traceback capturado
    assert 'Traceback' in row.trace
    assert 'tok_live_51H' not in row.trace
    assert 'tok_live_51H' not in row.message


def test_stamps_correlation_id_from_context(logger):
    set_correlation_id('deadbeefcafe')
    logger.info('within request')
    row = IrLogging.objects.get()
    assert row.correlation_id == 'deadbeefcafe'


def test_correlation_id_empty_outside_request(logger):
    clear_correlation_id()
    logger.info('no request')
    row = IrLogging.objects.get()
    assert row.correlation_id == ''


def test_anti_recursion_skips_django_db(logger):
    record = logging.LogRecord(
        name='django.db.backends', level=logging.DEBUG, pathname=__file__,
        lineno=1, msg='SELECT 1', args=(), exc_info=None,
    )
    DatabaseLogHandler().emit(record)
    assert IrLogging.objects.count() == 0


def test_non_blocking_on_insert_failure(logger):
    with mock.patch.object(IrLogging.objects, 'create', side_effect=RuntimeError('db down')):
        # No debe propagar la excepcion (DEC-LOG-04).
        logger.error('something broke')
    assert IrLogging.objects.count() == 0
