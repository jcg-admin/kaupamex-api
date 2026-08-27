"""Tests unitarios — ``custom_exception_handler`` (SOL-011 T-04, ADR-019).

Verifican que el handler:

- delega en el handler de DRF (el cuerpo de respuesta al cliente no cambia),
- emite el error por el canal de logging con el nivel derivado del estado
  HTTP: ``>= 500`` es ``ERROR`` con traceback, ``4xx`` es ``WARNING`` sin él,
- redacta el detalle en el origen (DEC-LOG-03 Nivel 1),
- es no bloqueante: un fallo al emitir no altera la respuesta (DEC-LOG-04),
- aterriza en ``ir.logging`` cuando el ``DatabaseLogHandler`` está enchufado.

**Reescritos con DEC-AF-11.** Vivían en ``tests/unit/core/`` y asertaban sobre
``get_request_error()`` —el ``ContextVar`` que sellaba el error para que
``RequestLogMiddleware`` lo copiara a una fila de ``RequestLog``—. Retirado
``RequestLog``, ese ContextVar se quedó sin lector y el handler emite por el
logger ``django.request``. El sujeto del test cambia con él: se mide el
``LogRecord``, no un sello intermedio.

El último test toca DB (``IrLogging``) → ``django_db``. Los tres primeros no:
``caplog`` intercepta el registro sin persistirlo, que es lo que corresponde
en la suite —``testing.py`` sustituye ``LOGGING`` por ``NullHandler``, así que
el handler ``db`` no corre por sí solo.

**El árbol de logging ya viene vivo en la suite** desde que ``testing.py``
declara ``disable_existing_loggers: False`` (H-API-749, cerrado por #617).
Hasta entonces ``django.request`` quedaba con ``disabled = True`` y una fixture
autouse de este mismo archivo lo reabría caso por caso — un parche local a un
defecto global: los otros catorce loggers apagados seguían mudos y nadie los
reabría. Estos tres casos son ahora el **control positivo** de que el árbol
está vivo: si alguien revierte la clave, fallan aquí.
"""
import logging
from unittest import mock

import pytest
from rest_framework import exceptions
from rest_framework.test import APIRequestFactory

from addons.base.exception_handling import custom_exception_handler
from addons.base.models import IrLogging
from tools.logging_context import clear_correlation_id, new_correlation_id
from tools.logging_handlers import DatabaseLogHandler

pytestmark = [pytest.mark.unit]

LOGGER = 'django.request'


def test_the_logging_tree_is_alive_in_the_suite():
    """El control que sostiene a los tres siguientes.

    Sin esto, un ``disable_existing_loggers: True`` los volvería a apagar y
    fallarían por ``caplog`` vacío — un síntoma que se lee como «el handler no
    emite». Aquí falla la causa, con su nombre.
    """
    assert not logging.getLogger(LOGGER).disabled
    # No es el único: `dictConfig` apagaba de golpe todo el árbol de Django.
    assert not logging.getLogger('django').disabled
    assert not logging.getLogger('django.db.backends').disabled


def test_delegates_to_drf_and_logs_the_error(caplog):
    exc = exceptions.ValidationError('invalid password=hunter2')
    ctx = {'request': APIRequestFactory().post('/x'), 'view': None}

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        resp = custom_exception_handler(exc, ctx)

    # Cuerpo cliente intacto: es la respuesta 400 del handler por defecto de DRF.
    assert resp is not None
    assert resp.status_code == 400

    registro = caplog.records[-1]
    assert registro.levelno == logging.WARNING     # 4xx no es fallo del servidor
    assert registro.exc_info is None               # ...y su pila no aporta
    assert 'ValidationError' in registro.getMessage()
    assert '/x' in registro.getMessage()
    assert 'hunter2' not in registro.getMessage()  # redactado en el origen


def test_server_error_is_error_level_with_traceback(caplog):
    exc = exceptions.APIException('charge failed card_token=tok_live_51H')

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        resp = custom_exception_handler(
            exc, {'request': APIRequestFactory().get('/x')})

    assert resp.status_code == 500
    registro = caplog.records[-1]
    assert registro.levelno == logging.ERROR
    assert registro.exc_info is not None           # 500 sí lleva traceback
    assert 'tok_live_51H' not in registro.getMessage()


def test_non_blocking_on_logging_failure():
    exc = exceptions.NotFound('missing')
    with mock.patch(
        'addons.base.exception_handling._emit',
        side_effect=RuntimeError('canal roto'),
    ):
        resp = custom_exception_handler(
            exc, {'request': APIRequestFactory().get('/x')})

    # La respuesta de DRF se devuelve intacta pese al fallo de la emisión.
    assert resp is not None
    assert resp.status_code == 404


@pytest.mark.django_db
def test_error_lands_in_ir_logging_through_the_db_handler():
    """El extremo del canal: el registro emitido acaba en ``ir.logging``.

    Se enchufa el handler a mano porque ``testing.py`` deja el árbol de logging
    en ``NullHandler``; en producción lo enchufa ``LOGGING['loggers']['django']``.
    """
    cid = new_correlation_id()
    handler = DatabaseLogHandler()
    logger = logging.getLogger(LOGGER)
    logger.addHandler(handler)
    nivel_previo = logger.level
    logger.setLevel(logging.WARNING)
    try:
        custom_exception_handler(
            exceptions.NotFound('sin producto'),
            {'request': APIRequestFactory().get('/api/v2/catalogue/products/9')},
        )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(nivel_previo)
        clear_correlation_id()

    fila = IrLogging.objects.get(correlation_id=cid)
    assert fila.level == IrLogging.LEVEL_WARNING
    assert 'NotFound' in fila.message
    assert '/api/v2/catalogue/products/9' in fila.message
