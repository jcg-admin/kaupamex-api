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
import select
import signal
import subprocess
import sys
import threading
import time
from datetime import timedelta
from pathlib import Path

import pytest
from django.db import connection, transaction
from django.utils import timezone

from addons.base.models import IrActionsServer, IrCron, SystemParameter
from orm.environments import get_current_uid
from tests.subprocess_env import subprocess_env

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / 'src'


@pytest.fixture(autouse=True)
def _tabla_de_crons_vacia(db):
    """``_process_jobs`` cuenta TODA la tabla; el test sólo posee sus filas.

    Cuatro data-migrations siembran un ``ir.cron`` cada una — ``helpdesk``,
    ``loyalty``, ``mail`` y ``observability``. Si están presentes,
    ``_process_jobs()`` devuelve 4 de más y ``assert procesados == 1`` falla
    con ``5 == 1``. Si no lo están, pasa. Cuál de las dos ocurre lo decide el
    ``flush`` de un ``TransactionTestCase`` anterior, es decir **el orden de
    la suite** — el mismo mecanismo de :ref:`h-api-337` visto desde el otro
    lado.

    Por eso el archivo pasaba aislado y fallaba en la suite completa: no es
    un test frágil por azar, es un test que mide una tabla global y afirma
    sobre ella como si fuera suya. Vaciarla al entrar hace que el número
    signifique lo que el test cree que significa.
    """
    IrCron.objects.all().delete()


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
    # La fuente trunca a segundos —``now.replace(microsecond=0)`` en
    # ``_reschedule_later`` (``odoo19c: ir_cron.py:637``)— asi que el
    # ``lastcall`` puede quedar por debajo de ``antes`` por microsegundos.
    # Comparar sin truncar medía el redondeo, no la reprogramacion.
    assert cron.lastcall >= antes.replace(microsecond=0)


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
    """``_process_job`` en aislamiento (sin pasar por ``_process_jobs``): la
    excepcion del callback se atrapa y de todos modos se reprograma.

    Llama a ``_process_job`` y no a ``_run_job`` porque desde el porte
    completo esos son dos metodos distintos, como en la fuente: ``_run_job``
    corre el bucle y **devuelve** el desenlace; quien reprograma segun ese
    desenlace es ``_process_job``."""
    def _falla(cls):
        raise RuntimeError('boom')

    monkeypatch.setattr(SystemParameter, 'boom_test', classmethod(_falla), raising=False)
    cron = _cron_listo(method_name='boom_test')
    nextcall_previo = cron.nextcall

    with transaction.atomic():
        IrCron._process_job(cron)  # NO debe lanzar

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
        env=subprocess_env(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


def _wait_until_it_handles_signals(proc, timeout=60):
    """Espera a que el worker anuncie que ya instaló sus handlers.

    Espera **la condición**, no una duración. La versión anterior de este
    archivo hacía ``proc.wait(timeout=2)`` y mandaba SIGTERM al expirar; esos
    2 s son el arranque de Django, que en una máquina ociosa sobran y bajo
    carga no alcanzan. Cuando no alcanzan, la señal llega **antes** de que el
    handler exista, el proceso muere con la disposición por defecto
    (``returncode`` −15) y el test se pone rojo sin que el código haya
    cambiado: un rojo que no distingue «el apagado limpio está roto» de «la
    máquina estaba ocupada». Ver :ref:`h-api-841`.

    :returns: la línea de disponibilidad ya consumida de ``stdout``.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            rest = proc.stdout.read()
            pytest.fail('cron termino solo antes de estar listo '
                        f'(returncode={proc.returncode}, stdout={rest!r})')
        ready, _, _ = select.select([proc.stdout], [], [], 0.5)
        if not ready:
            continue
        line = proc.stdout.readline()
        if 'worker' in line and 'activo' in line:
            return line
    proc.kill()
    pytest.fail(f'cron no anuncio disponibilidad en {timeout}s')


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
    # La señal se manda cuando el worker DICE que ya la atiende, no tras una
    # espera fija — la precondición del caso es que el handler exista.
    _wait_until_it_handles_signals(proc)

    proc.send_signal(signal.SIGTERM)
    try:
        salida, error = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail('cron no salio dentro de 10s tras SIGTERM')

    assert proc.returncode == 0, f'stdout={salida!r} stderr={error!r}'
    assert 'saliendo limpio' in salida


# --- el scope de usuario (H-API-333, tarea #127) ----------------------------

def test_callback_corre_bajo_el_usuario_del_cron(monkeypatch, django_user_model):
    """El equivalente del ``env = api.Environment(job_cr, job['user_id'], …)``
    de la referencia (``odoo19c: ir_cron.py:481-483``): dentro del método
    invocado, ``get_current_user()`` debe ser el ``user`` del cron.

    Antes de #127 este eje existía (``orm/environments.py:114``) pero el cron
    no lo poblaba: el campo se persistía y no cambiaba nada."""
    visto = {}
    monkeypatch.setattr(
        SystemParameter, 'noop_test',
        classmethod(lambda cls: visto.update(uid=get_current_uid())),
        raising=False,
    )
    usuario = django_user_model.objects.create_user(
        login='cron.operador@kaupamex.test', password='x')
    cron = _cron_listo()
    cron.user = usuario
    cron.save(update_fields=['user'])

    assert IrCron._process_jobs() == 1
    assert visto['uid'] == usuario.pk, (
        'el callback debe correr bajo el usuario del cron, no con el uid del '
        'proceso worker'
    )


def test_el_scope_se_restaura_al_salir_del_callback(monkeypatch, django_user_model):
    """``user_scope`` es un contextmanager que **restaura** el valor previo.
    Sin eso, el usuario de un job se filtraría al siguiente — y a todo lo que
    corriera después en el mismo proceso worker."""
    monkeypatch.setattr(
        SystemParameter, 'noop_test', classmethod(lambda cls: None), raising=False)
    usuario = django_user_model.objects.create_user(
        login='cron.otro@kaupamex.test', password='x')
    cron = _cron_listo()
    cron.user = usuario
    cron.save(update_fields=['user'])

    previo = get_current_uid()
    assert IrCron._process_jobs() == 1
    assert get_current_uid() == previo, (
        'el uid previo debe restaurarse: un job no puede dejar su usuario '
        'puesto para el siguiente'
    )


def test_cron_sin_usuario_deja_el_scope_en_none(monkeypatch):
    """Con ``user`` nulo el scope se fija a ``None`` — el mismo estado que
    tiene el proceso worker. Se pone el contextmanager igual para no tener dos
    caminos, y esto lo comprueba."""
    visto = {}
    monkeypatch.setattr(
        SystemParameter, 'noop_test',
        classmethod(lambda cls: visto.update(uid=get_current_uid())),
        raising=False,
    )
    cron = _cron_listo()
    assert cron.user_id is None

    assert IrCron._process_jobs() == 1
    assert visto['uid'] is None
