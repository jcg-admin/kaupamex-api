"""Contrato del runner de ``IrCron`` (``_acquire_one_job``/``_run_job``/
``_process_jobs``/``_callback``) y del subcomando ``cron`` — iniciativa
``adaptar-familias-odoo-monolito-modular`` (SOL-096, H-BASE-01 C-2).

Verifica, en los dos sentidos donde aplica:

- ``_process_jobs`` ejecuta el callback delegado (``model_name``/
  ``method_name``) de un job listo y reprograma su ``nextcall``/``lastcall``.
- ``_process_jobs`` NO toca un job cuyo ``nextcall`` aún no vence, ni uno
  ``active=False``.
- un job cuyo callback lanza excepción NO detiene el procesamiento de los
  siguientes jobs de la misma pasada, y de todos modos se reprograma
  (== la referencia: ``_reschedule_later`` corre para ``FULLY_DONE`` **y**
  ``FAILED`` por igual, ir_cron.py:445-448).
- ``_acquire_one_job`` respeta ``SKIP LOCKED``: con el row bloqueado por otra
  transacción real y concurrente, no espera y devuelve ``None``.
- el subcomando ``kaupamex-bin cron`` (``manage.py cron``) sale limpio
  (código 0) ante ``SIGTERM`` sin esperar el intervalo completo.

Toca DB → django_db (algunas, ``transaction=True`` para el test de
concurrencia real entre hilos).
"""
import signal
import subprocess
import sys
import threading
from datetime import timedelta
from pathlib import Path

import pytest
from django.db import connection, transaction
from django.utils import timezone

from addons.base.models import IrActionsServer, IrCron, SystemParameter

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / 'src'


def _accion(name='Tarea', model_name='base.SystemParameter', method_name='noop_test'):
    """== ``_accion`` de ``test_ir_cron.py``: crea la ``ir.actions.server``
    en la que el cron delega su "qué ejecutar". Aquí ``model_name`` apunta a
    un modelo real (``SystemParameter``) para que ``_callback`` pueda
    resolverlo con ``apps.get_model`` de verdad.

    ``path=None`` explícito (no el default ``''`` de ``IrActionsBase``): dos
    acciones en el mismo test con ``path=''`` chocan contra su UNIQUE —
    ``NULL`` sí admite múltiples filas."""
    return IrActionsServer.objects.create(
        name=name, model_name=model_name, method_name=method_name, state='code',
        path=None,
    )


def _cron_listo(model_name='base.SystemParameter', method_name='noop_test',
                 priority=5, active=True, nextcall_delta=timedelta(minutes=-5)):
    return IrCron.objects.create(
        ir_actions_server=_accion(model_name=model_name, method_name=method_name),
        nextcall=timezone.now() + nextcall_delta,
        priority=priority,
        active=active,
    )


# --- _process_jobs ejecuta el callback y reprograma -------------------------

def test_process_jobs_ejecuta_callback_y_reprograma(monkeypatch):
    llamadas = []
    monkeypatch.setattr(
        SystemParameter, 'noop_test', classmethod(lambda cls: llamadas.append(1)),
        raising=False,
    )
    cron = _cron_listo()
    nextcall_previo = cron.nextcall
    antes = timezone.now()

    procesados = IrCron._process_jobs()

    assert procesados == 1
    assert llamadas == [1]
    cron.refresh_from_db()
    assert cron.nextcall > nextcall_previo, 'nextcall debe avanzar tras procesar el job'
    assert cron.nextcall > antes, 'el nuevo nextcall debe superar "ahora"'
    assert cron.lastcall is not None
    assert cron.lastcall >= antes


def test_process_jobs_no_toca_job_con_nextcall_futuro(monkeypatch):
    llamadas = []
    monkeypatch.setattr(
        SystemParameter, 'noop_test', classmethod(lambda cls: llamadas.append(1)),
        raising=False,
    )
    cron = _cron_listo(nextcall_delta=timedelta(minutes=5))  # futuro: no listo
    nextcall_previo = cron.nextcall

    procesados = IrCron._process_jobs()

    assert procesados == 0
    assert llamadas == []
    cron.refresh_from_db()
    assert cron.nextcall == nextcall_previo


def test_process_jobs_no_toca_job_inactivo(monkeypatch):
    llamadas = []
    monkeypatch.setattr(
        SystemParameter, 'noop_test', classmethod(lambda cls: llamadas.append(1)),
        raising=False,
    )
    _cron_listo(active=False)

    procesados = IrCron._process_jobs()

    assert procesados == 0
    assert llamadas == []


# --- un job que falla no bloquea a los siguientes ---------------------------

def test_job_que_falla_no_bloquea_a_los_siguientes(monkeypatch):
    def _falla(cls):
        raise RuntimeError('fallo deliberado del callback')

    llamadas_ok = []
    monkeypatch.setattr(SystemParameter, 'falla_test', classmethod(_falla), raising=False)
    monkeypatch.setattr(
        SystemParameter, 'ok_test', classmethod(lambda cls: llamadas_ok.append(1)),
        raising=False,
    )

    cron_falla = _cron_listo(method_name='falla_test', priority=1)
    cron_ok = _cron_listo(method_name='ok_test', priority=2)
    nextcall_falla_previo = cron_falla.nextcall
    nextcall_ok_previo = cron_ok.nextcall

    procesados = IrCron._process_jobs()

    # Ambos jobs se procesan (el orden es por priority: falla primero).
    assert procesados == 2
    assert llamadas_ok == [1], 'el segundo job debe correr aunque el primero falle'

    cron_falla.refresh_from_db()
    cron_ok.refresh_from_db()
    # El job que fallo tambien se reprograma — no queda "atascado".
    assert cron_falla.nextcall > nextcall_falla_previo
    assert cron_falla.lastcall is not None
    assert cron_ok.nextcall > nextcall_ok_previo


def test_run_job_no_propaga_la_excepcion_del_callback(monkeypatch):
    """``_run_job`` en aislamiento (sin pasar por ``_process_jobs``): la
    excepcion del callback se atrapa y de todos modos se reprograma."""
    def _falla(cls):
        raise RuntimeError('boom')

    monkeypatch.setattr(SystemParameter, 'boom_test', classmethod(_falla), raising=False)
    cron = _cron_listo(method_name='boom_test')
    nextcall_previo = cron.nextcall

    with transaction.atomic():
        cron._run_job()  # NO debe lanzar

    cron.refresh_from_db()
    assert cron.nextcall > nextcall_previo


# --- _acquire_one_job respeta SKIP LOCKED (concurrencia real) --------------

@pytest.mark.django_db(transaction=True)
def test_acquire_one_job_no_espera_ni_adquiere_row_bloqueado():
    """Con el row bloqueado por una transaccion real y concurrente (otro
    hilo, otra conexion), ``_acquire_one_job`` NO debe esperar ni adquirirlo
    — debe devolver ``None`` de inmediato (== SKIP LOCKED)."""
    cron = _cron_listo()

    lock_tomado = threading.Event()
    liberar_lock = threading.Event()
    error_en_hilo = []

    def mantener_lock():
        try:
            with transaction.atomic():
                (IrCron.objects
                 .select_for_update(skip_locked=True, no_key=True)
                 .filter(pk=cron.pk).first())
                lock_tomado.set()
                liberar_lock.wait(timeout=10)
        except Exception as exc:  # noqa: BLE001 — se reporta al hilo principal
            error_en_hilo.append(exc)
        finally:
            connection.close()

    hilo = threading.Thread(target=mantener_lock)
    hilo.start()
    try:
        assert lock_tomado.wait(timeout=5), 'el hilo no tomo el lock a tiempo'
        assert not error_en_hilo, f'el hilo de lock fallo: {error_en_hilo}'

        with transaction.atomic():
            adquirido = IrCron._acquire_one_job(cron.pk)
        assert adquirido is None, 'SKIP LOCKED debe devolver None, no esperar'
    finally:
        liberar_lock.set()
        hilo.join(timeout=10)
    assert not error_en_hilo, f'el hilo de lock fallo: {error_en_hilo}'

    # Liberado el lock, ahora si se adquiere normalmente.
    with transaction.atomic():
        adquirido = IrCron._acquire_one_job(cron.pk)
    assert adquirido is not None
    assert adquirido.pk == cron.pk


# --- El subcomando `cron` sale limpio ante SIGTERM --------------------------

def _correr_cron_subproceso(*extra_args):
    return subprocess.Popen(
        [sys.executable, 'manage.py', 'cron', *extra_args],
        cwd=str(SRC_DIR),
        env={
            'PATH': '/usr/bin:/bin',
            'DJANGO_SETTINGS_MODULE': 'config.settings.testing',
            'HOME': '/root',
        },
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


@pytest.mark.django_db(transaction=True)
def test_cron_command_una_pasada_sale_0():
    """``--once``: procesa una pasada sobre todas las bases y sale — sanity
    del contrato antes de probar la senal."""
    proc = _correr_cron_subproceso('--once')
    try:
        salida, error = proc.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail('cron --once no termino dentro de 60s')
    assert proc.returncode == 0, f'stdout={salida!r} stderr={error!r}'
    assert 'saliendo limpio' in salida


@pytest.mark.django_db(transaction=True)
def test_cron_command_sale_limpio_ante_sigterm():
    """Sin ``--once`` y con un intervalo largo, el proceso debe estar
    dormido cuando llega SIGTERM — y salir en segundos, no esperar el
    intervalo completo (30s)."""
    proc = _correr_cron_subproceso('--interval', '30')
    try:
        # Deja tiempo para que Django arranque, corra la primera pasada
        # (rapida, sin jobs listos) y entre a dormir.
        proc.wait(timeout=2)
        pytest.fail(
            'cron termino solo antes de recibir la señal '
            f'(returncode={proc.returncode})'
        )
    except subprocess.TimeoutExpired:
        # silent OK because el timeout ES la aserción: que `wait` expire
        # significa que el proceso sigue vivo y durmiendo, que es justo lo
        # que este test comprueba antes de mandarle SIGTERM. El caso de
        # fallo lo cubre el pytest.fail de arriba, al que se llega si el
        # proceso terminó solo.
        pass

    proc.send_signal(signal.SIGTERM)
    try:
        salida, error = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail('cron no salio dentro de 10s tras SIGTERM')

    assert proc.returncode == 0, f'stdout={salida!r} stderr={error!r}'
    assert 'saliendo limpio' in salida
