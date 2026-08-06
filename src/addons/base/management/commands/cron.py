"""``cron`` — el ``WorkerCron`` de la referencia, como subcomando (SOL-096,
H-BASE-01 C-2).

Equivalente de ``odoo19c: odoo/service/server.py`` (``class WorkerCron(Worker)``,
líneas 1404-1489) y de ``cron_database_list`` (línea 99, ``odoo-tools@622ddc2a``).

Por qué subcomando y no un worker de Gunicorn
----------------------------------------------

Gunicorn no puede alojar un worker de cron dentro del mismo pool HTTP: su
arbiter construye una **única** ``worker_class`` para todo el pool, atada a
``LISTENERS`` (``gunicorn/arbiter.py:687-691``), y sus seis clases de worker
son todas HTTP. La referencia en cambio lanza ``WorkerHTTP`` **y**
``WorkerCron`` desde el mismo arbiter (``service/server.py:1361``/``:1404``) —
un proceso especializado por rol, no un worker HTTP disfrazado.

Aquí la misma partición se resuelve como **subcomando aparte**
(``kaupamex-bin cron``), el mismo criterio que separa ``db``/``server`` de la
referencia (ver docstring de ``management/commands/server.py``): el servidor
web es un comando entre varios, no el programa. Un supervisor (systemd) lanza
``kaupamex-bin server`` y ``kaupamex-bin cron`` como dos procesos —y
credenciales— distintos.

Multi-base
----------

Recorre el plano L0 (``default``) más todas las bases ``company_<N>_db``
(``service.db.list_company_db_names`` + ``install_company_aliases``) — ==
``cron_database_list`` de la referencia (``config['db_name'] or
list_dbs(True)``) adaptado al modelo DB-per-company del proyecto: no hay un
único ``db_name`` de arranque, hay N bases, y cada una tiene su propia tabla
``ir_cron`` (SOL-091).

Bucle
-----

Sleep interrumpible entre pasadas (``--interval``, default 60s == referencia
``SLEEP_INTERVAL``, ``service/server.py:68``), límite de vida opcional
(``--max-age`` == referencia ``limit_time_worker_cron``, default 0 = sin
límite) y salida limpia ante ``SIGTERM``/``SIGINT`` (== ``Worker.
signal_handler``, ``service/server.py:1254``: no procesa la señal en el
momento, sólo baja una bandera que el loop revisa entre pasadas y durante el
sleep).

Deliberadamente NO se porta (colapsado en el modelo de proceso único de
Gunicorn + systemd)
---------------------------------------------------------------------------

- **Watchdog / múltiples procesos worker** (``multi.pipe_ping`` / los checks
  de memoria y CPU de ``Worker.check_limits``): el supervisor del proceso
  (systemd) es quien reinicia este comando si muere o excede memoria — mismo
  criterio que ``service/server.py`` ya documenta para
  ``set_limit_memory_hard``.
- **LISTEN/NOTIFY** (canal ``cron_trigger``): sin ``ir.cron.trigger`` no hay a
  qué reaccionar (ver docstring de ``ir_cron.py``); el polling por intervalo
  fijo lo reemplaza — mismo colapso que ``_notifydb`` en el módulo del
  modelo.
- **Cola de bases priorizada por notificación** (``self.db_queue`` con las
  bases notificadas primero): sin LISTEN/NOTIFY no hay orden de prioridad que
  aplicar; cada pasada recorre las bases en el mismo orden.
"""
import logging
import signal
import time

from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connections

from addons.base.models import IrCron
from service.db import install_company_aliases, list_company_db_names

logger = logging.getLogger(__name__)

#: == referencia SLEEP_INTERVAL (odoo19c: odoo/service/server.py:68).
_DEFAULT_INTERVAL = 60
#: Granularidad del sleep interrumpible — cuánto tarda como máximo en notar
#: que la bandera de parada bajó tras una señal.
_SLEEP_STEP = 1.0


class Command(BaseCommand):
    help = (
        'Worker de ir.cron: hace polling de tareas programadas listas en el '
        'plano L0 y en cada base company_<N>_db, y las ejecuta. Equivalente '
        'de WorkerCron (odoo19c: odoo/service/server.py:1404).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval', type=float, default=_DEFAULT_INTERVAL,
            help=(
                'Segundos entre pasadas (default: %d, == SLEEP_INTERVAL de '
                'la referencia).' % _DEFAULT_INTERVAL
            ),
        )
        parser.add_argument(
            '--max-age', type=float, default=0,
            help=(
                'Segundos de vida máxima del worker antes de salir '
                '(0 = sin límite, == limit_time_worker_cron de la '
                'referencia).'
            ),
        )
        parser.add_argument(
            '--once', action='store_true',
            help=(
                'Procesa una sola pasada sobre todas las bases y sale (para '
                'invocación externa vía cron del SO, o para tests).'
            ),
        )

    def handle(self, *args, **options):
        self._alive = True
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)

        interval = options['interval']
        max_age = options['max_age']
        once = options['once']
        start = time.monotonic()

        while self._alive:
            self._process_pass()
            if once:
                break
            if max_age > 0 and (time.monotonic() - start) >= max_age:
                self.stdout.write(
                    'cron: edad maxima (%ss) alcanzada, saliendo' % max_age)
                break
            if not self._alive:
                break
            self._sleep(interval)

        self.stdout.write(self.style.SUCCESS('cron: saliendo limpio'))

    def _stop(self, signum, frame):
        """Handler de SIGTERM/SIGINT (== ``Worker.signal_handler`` de la
        referencia, ``service/server.py:1254``): no interrumpe nada en el
        momento — sólo baja la bandera que ``handle()``/``_sleep()``
        revisan, para que la pasada en curso (si hay una) termine limpia
        antes de salir."""
        self._alive = False

    def _sleep(self, seconds):
        """Sleep interrumpible en pasos de ``_SLEEP_STEP`` (== la referencia
        usa ``select()`` sobre un ``wakeup_fd`` que la señal desbloquea de
        inmediato; aquí no hay ese fd, y desde Python 3.5 (PEP 475) un
        ``time.sleep(N)`` NO se interrumpe por una señal cuyo handler sólo
        baja una bandera — la syscall se reintenta automáticamente. Este
        loop es el reemplazo: la espera nunca dura más de ``_SLEEP_STEP``
        tras la señal, sin depender de ese comportamiento de bajo nivel."""
        remaining = seconds
        while remaining > 0 and self._alive:
            step = min(_SLEEP_STEP, remaining)
            time.sleep(step)
            remaining -= step

    def _process_pass(self):
        """Una pasada sobre todas las bases (== ``process_work`` de
        ``WorkerCron``, ``service/server.py:1439-1471``, colapsado: la
        referencia procesa UNA base por invocación y deja que el loop
        externo la llame de nuevo por cada base en ``self.db_queue``; aquí
        una pasada agota la cola completa en el mismo ciclo, porque no hay
        LISTEN/NOTIFY que priorice bases notificadas — ver docstring del
        módulo)."""
        company_dbs = list_company_db_names(using=DEFAULT_DB_ALIAS)
        if company_dbs:
            install_company_aliases(
                connections.databases, names=company_dbs, using=DEFAULT_DB_ALIAS)
        for db_name in [DEFAULT_DB_ALIAS] + company_dbs:
            self._process_database(db_name)

    def _process_database(self, db_name):
        """Procesa una base. Una excepción aquí (base inalcanzable, tabla
        ``ir_cron`` ausente porque la base aún no aplicó las migraciones de
        ``base``) no debe tumbar el worker ni impedir procesar las demás
        bases de la pasada — == la referencia: ``_process_jobs`` atrapa
        ``BadVersion``/``BadModuleState``/``UndefinedTable`` por-base, sin
        abortar el recorrido de ``cron_database_list`` (ver docstring de
        ``ir_cron.py`` sobre por qué esas dos primeras no se portaron)."""
        try:
            processed = IrCron._process_jobs(using=db_name)
        except Exception:
            logger.exception('cron: fallo procesando la base %s', db_name)
            return
        if processed:
            self.stdout.write(
                'cron: %d job(s) procesados en %s' % (processed, db_name))
