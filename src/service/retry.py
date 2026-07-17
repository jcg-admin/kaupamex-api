"""Reintento ante concurrencia de BD — ``service/retry.py``.

Adaptado del patrón de ``odoo/service/model.py::retrying`` (Odoo Community
``odoo19x``, LGPL-3) — atribución preservada. Bajo DEC-KX-03, la fuente LGPL-3
permitiría **copia near-verbatim** con cumplimiento; aquí se eligió la
**reimplementación nativa** del patrón (más conservadora y desacoplada del
cursor/env/registry de Odoo). Mismo resultado funcional, distinto mecanismo
(DEC-KX-03 punto 3).

Odoo envuelve cada request en un loop que reintenta la
transacción ante un *serialization failure* / deadlock, con rollback + backoff
exponencial aleatorio (``random.uniform(0.0, 2**tryno)``,
``MAX_TRIES_ON_CONCURRENCY_FAILURE = 5``). Aquí se extrae **solo el patrón**
—loop + detección de error de concurrencia + backoff con jitter— desacoplado del
cursor/env/registry propios de Odoo, contra el ``OperationalError`` de Django y
los códigos de MariaDB.

Motivación (H-API-INFRA-01): el proyecto ya sufre el deadlock 1213 de MariaDB —
``pytest.ini`` lo mitiga con ``-p no:randomly`` (orden determinista), pero **no
existe** ningún reintento en producción, pese al uso extenso de
``select_for_update()`` en rutas de alta contención (payments/webhooks,
refunds, cart, orders, inventory).

CONTRATO DE SEGURIDAD (obligatorio al usar el decorador)
--------------------------------------------------------
El reintento **re-ejecuta la función completa**. Por eso la función decorada
DEBE:

1. Envolver **su propia** ``transaction.atomic()`` (cada reintento abre una
   transacción nueva; un deadlock aborta la anterior).
2. Ser **DB-only e idempotente respecto a I/O externo**: NUNCA envolver una
   llamada a un gateway de pago u otra I/O con efectos (un deadlock reintentado
   volvería a llamar al gateway → doble cobro/reembolso). Envolver el bloque de
   BD, no la I/O.

Es un decorador (Tell-Don't-Ask: el llamador "ejecuta" la operación y el
decorador gobierna el reintento; el llamador no inspecciona códigos de error).
``sleep``/``rng`` son inyectables para pruebas deterministas.
"""
import functools
import logging
import random
import time

from django.db.utils import OperationalError

logger = logging.getLogger(__name__)

#: Códigos de error de MariaDB que indican concurrencia transitoria (reintentables).
DEADLOCK = 1213            # ER_LOCK_DEADLOCK — deadlock found, transaction rolled back.
LOCK_WAIT_TIMEOUT = 1205   # ER_LOCK_WAIT_TIMEOUT — lock wait timeout exceeded.
_RETRYABLE_CODES = frozenset({DEADLOCK, LOCK_WAIT_TIMEOUT})

#: Igual que ``MAX_TRIES_ON_CONCURRENCY_FAILURE`` de Odoo.
DEFAULT_MAX_TRIES = 5


def _is_concurrency_error(exc):
    """¿El ``OperationalError`` es un deadlock/lock-timeout reintentable?

    El primer arg de ``MySQLdb.OperationalError`` (que Django re-emite como
    ``django.db.utils.OperationalError``) es el ``errno`` de MariaDB.
    """
    code = exc.args[0] if exc.args else None
    return code in _RETRYABLE_CODES


def retry_on_db_concurrency_error(func=None, *, max_tries=DEFAULT_MAX_TRIES,
                                  sleep=time.sleep, rng=random):
    """Reintenta la función decorada ante deadlock/lock-timeout de MariaDB.

    Backoff exponencial con jitter (``rng.uniform(0.0, 2**tryno)``), hasta
    ``max_tries`` intentos; agotados, re-lanza el último ``OperationalError``.
    Un ``OperationalError`` no-concurrencia (o cualquier otra excepción) se
    propaga en el primer intento, sin reintento.

    Ver el CONTRATO DE SEGURIDAD del módulo: decorar solo operaciones de BD que
    abran su propia ``transaction.atomic()`` y no incluyan I/O externa.

    Uso::

        @retry_on_db_concurrency_error
        def settle(...):
            with transaction.atomic():
                ...

        @retry_on_db_concurrency_error(max_tries=3)
        def adjust(...):
            with transaction.atomic():
                ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for tryno in range(1, max_tries + 1):
                try:
                    return fn(*args, **kwargs)
                except OperationalError as exc:
                    if not _is_concurrency_error(exc) or tryno == max_tries:
                        if _is_concurrency_error(exc):
                            logger.warning(
                                'Concurrencia BD (%s) en %s: agotados %d intentos.',
                                exc.args[0] if exc.args else '?', fn.__name__, max_tries,
                            )
                        raise
                    wait = rng.uniform(0.0, 2 ** tryno)
                    logger.warning(
                        'Concurrencia BD (%s) en %s: reintento %d/%d en %.3fs.',
                        exc.args[0] if exc.args else '?', fn.__name__,
                        tryno, max_tries, wait,
                    )
                    sleep(wait)
            raise RuntimeError('unreachable')  # pragma: no cover
        return wrapper

    # Permite ``@retry_on_db_concurrency_error`` (sin paréntesis) y
    # ``@retry_on_db_concurrency_error(max_tries=..., ...)``.
    return decorator(func) if func is not None else decorator
