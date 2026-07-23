"""
Tests — service.retry (reintento ante concurrencia de BD).

Adaptación nativa de ``odoo/service/model.py::retrying`` (H-API-INFRA-01):
reintenta una operación **de BD** ante deadlock (1213) o lock-wait-timeout
(1205) de MariaDB, con backoff exponencial + jitter. Errores no-concurrencia
(o no ``OperationalError``) NO se reintentan. ``sleep``/``rng`` se inyectan para
que el test sea determinista y sin esperas reales.
"""
from django.db.utils import OperationalError

import pytest

from service.retry import (
    DEADLOCK, LOCK_WAIT_TIMEOUT, retry_on_db_concurrency_error,
)

pytestmark = pytest.mark.unit


class _Spy:
    """rng/sleep espía: registra las llamadas y no espera de verdad."""

    def __init__(self):
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)

    def uniform(self, lo, hi):
        # jitter determinista para el test: el tope del rango.
        return hi


def _deadlock():
    return OperationalError(DEADLOCK, 'Deadlock found when trying to get lock')


def test_success_first_try_no_sleep():
    spy = _Spy()
    calls = []

    @retry_on_db_concurrency_error(sleep=spy.sleep, rng=spy)
    def op():
        calls.append(1)
        return 'ok'

    assert op() == 'ok'
    assert len(calls) == 1
    assert spy.sleeps == []


def test_retries_deadlock_then_succeeds():
    spy = _Spy()
    calls = []

    @retry_on_db_concurrency_error(max_tries=5, sleep=spy.sleep, rng=spy)
    def op():
        calls.append(1)
        if len(calls) < 3:
            raise _deadlock()
        return 'ok'

    assert op() == 'ok'
    assert len(calls) == 3         # 2 fallos + 1 éxito
    assert len(spy.sleeps) == 2    # esperó entre reintentos
    # Backoff exponencial: 2**1=2, 2**2=4 (tope del jitter espiado).
    assert spy.sleeps == [2, 4]


def test_reraises_after_max_tries():
    spy = _Spy()
    calls = []

    @retry_on_db_concurrency_error(max_tries=3, sleep=spy.sleep, rng=spy)
    def op():
        calls.append(1)
        raise _deadlock()

    with pytest.raises(OperationalError):
        op()
    assert len(calls) == 3         # agotó los intentos
    assert len(spy.sleeps) == 2    # durmió entre los 3 intentos (no tras el último)


def test_lock_wait_timeout_is_retried():
    spy = _Spy()
    calls = []

    @retry_on_db_concurrency_error(sleep=spy.sleep, rng=spy)
    def op():
        calls.append(1)
        if len(calls) < 2:
            raise OperationalError(LOCK_WAIT_TIMEOUT, 'Lock wait timeout exceeded')
        return 'ok'

    assert op() == 'ok'
    assert len(calls) == 2


def test_non_concurrency_operational_error_not_retried():
    spy = _Spy()
    calls = []

    @retry_on_db_concurrency_error(sleep=spy.sleep, rng=spy)
    def op():
        calls.append(1)
        raise OperationalError(1146, "Table 'x' doesn't exist")

    with pytest.raises(OperationalError):
        op()
    assert len(calls) == 1         # no reintentó un error no-concurrencia
    assert spy.sleeps == []


def test_non_operational_error_propagates_immediately():
    spy = _Spy()
    calls = []

    @retry_on_db_concurrency_error(sleep=spy.sleep, rng=spy)
    def op():
        calls.append(1)
        raise ValueError('boom')

    with pytest.raises(ValueError):
        op()
    assert len(calls) == 1
    assert spy.sleeps == []


def test_preserves_wrapped_metadata():
    @retry_on_db_concurrency_error
    def my_operation():
        """docstring de op."""
        return 1

    assert my_operation.__name__ == 'my_operation'
    assert my_operation.__doc__ == 'docstring de op.'


def test_bare_decorator_without_parens():
    calls = []

    @retry_on_db_concurrency_error
    def op():
        calls.append(1)
        return 'ok'

    assert op() == 'ok'
    assert len(calls) == 1
