#!/usr/bin/env python3
"""Prueba: ¿puede el master de Gunicorn alojar un proceso lateral (cron)?

Origen: directiva del ejecutor 2026-08-11 — *"¿lo probaste? si mencionaste que
no se puede hacer, se requiere su análisis que efectivamente no se puede hacer;
de igual manera, debes de guardar el código de las pruebas"*. Es
``porte-completo-no-parcial.md`` aplicado: *"«imposible» exige el intento"*.

La afirmación auditada, heredada del docstring de
``src/addons/base/management/commands/cron.py`` y repetida en
``setup/kaupamex.service`` y en el análisis de docs:

    "Gunicorn no puede alojar un worker de cron dentro del mismo pool HTTP:
     su arbiter construye una única ``worker_class`` para todo el pool"

Lo que esta prueba mide, y por qué la afirmación necesitaba matizarse:

1. **El pool HTTP sí es homogéneo.** ``arbiter.py:687-691`` instancia
   ``self.worker_class(...)`` —una sola clase— atada a ``self.LISTENERS``.
   Esa mitad de la afirmación es correcta.
2. **Pero el master NO está cerrado.** ``arbiter.py:162`` invoca
   ``cfg.on_starting(self)`` y ``:199`` invoca ``cfg.when_ready(self)``, ambos
   en el proceso master. Desde ahí se puede lanzar un proceso lateral. Así que
   *alojar* un cron **sí es posible** — la afirmación absoluta era falsa.
3. **Lo que decide es qué pasa al apagar.** Si el hijo lanzado por el hook
   sobrevive al ``SIGTERM`` del master, queda huérfano: systemd da la unidad
   por detenida mientras el cron sigue vivo, tocando la base. Ése —y no una
   imposibilidad— es el argumento medible para la unidad separada.

Uso::

    .venv/bin/python scripts/probe_gunicorn_side_process.py

Sale 0 si la prueba pudo ejecutarse (sea cual sea el veredicto) y 1 si no pudo
montarse el experimento. El veredicto se imprime; no se infiere.
"""
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

VENV_GUNICORN = Path(__file__).resolve().parents[1] / '.venv' / 'bin' / 'gunicorn'

# App WSGI mínima — la pregunta es del arbiter, no de Django. Meter Django aquí
# mezclaría dos variables (arranque del ORM y hospedaje del proceso lateral).
APP = '''
def application(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [b'ok']
'''

# El hook corre en el MASTER. Lanza un hijo que late a un archivo: si el archivo
# sigue creciendo tras matar al master, el hijo quedó huérfano.
CONF = '''
import os, sys, time

bind = '127.0.0.1:{port}'
workers = 2
worker_class = 'sync'
proc_name = 'probe-gunicorn'

def when_ready(server):
    """Hook del arbiter (arbiter.py:199) — corre en el master."""
    pid = os.fork()
    if pid == 0:
        # Hijo: el "cron". Late cada 0.2 s hasta que lo maten.
        with open({latido!r}, 'a', buffering=1) as fh:
            fh.write('cron-vivo pid=%d\\n' % os.getpid())
            while True:
                time.sleep(0.2)
                fh.write('latido %f\\n' % time.time())
    else:
        with open({pidfile!r}, 'w') as fh:
            fh.write(str(pid))
'''


def main():
    if not VENV_GUNICORN.is_file():
        print(f'gunicorn no encontrado en {VENV_GUNICORN}', file=sys.stderr)
        return 1

    workdir = Path(tempfile.mkdtemp(prefix='probe-gunicorn-'))
    latido = workdir / 'latido.txt'
    pidfile = workdir / 'cron.pid'
    (workdir / 'app.py').write_text(APP)
    (workdir / 'conf.py').write_text(
        CONF.format(port=8099, latido=str(latido), pidfile=str(pidfile)))

    print(f'workdir: {workdir}')
    proc = subprocess.Popen(
        [str(VENV_GUNICORN), '-c', 'conf.py', 'app:application'],
        cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    # Esperar a que el hook haya corrido y el hijo esté latiendo.
    for _ in range(50):
        time.sleep(0.1)
        if pidfile.is_file() and latido.is_file():
            break

    if not pidfile.is_file():
        proc.kill()
        print('RESULTADO: el hook when_ready NO llego a lanzar el hijo.')
        print(proc.communicate()[0][:2000])
        return 1

    cron_pid = int(pidfile.read_text().strip())
    print(f'master pid={proc.pid} | proceso lateral pid={cron_pid}')
    print(f'HALLAZGO 1 — el master SI puede alojar un proceso lateral: '
          f'{"vivo" if pid_vivo(cron_pid) else "muerto"}')

    latidos_antes = latido.read_text().count('latido')

    # Apagado limpio, como haria systemd.
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

    time.sleep(1.0)
    huerfano = pid_vivo(cron_pid)
    latidos_despues = latido.read_text().count('latido')

    print(f'\ntras SIGTERM al master: proceso lateral '
          f'{"SIGUE VIVO (huerfano)" if huerfano else "murio con el master"}')
    print(f'latidos antes={latidos_antes} despues={latidos_despues} '
          f'(crecio={latidos_despues > latidos_antes})')

    if huerfano:
        print('\nVEREDICTO: alojarlo es POSIBLE pero el hijo queda HUERFANO al')
        print('apagar. systemd daria la unidad por detenida con el cron vivo')
        print('tocando la base. La unidad separada no es un rodeo: es lo que')
        print('pone el ciclo de vida del cron bajo el supervisor.')
        if pid_vivo(cron_pid):
            os.kill(cron_pid, signal.SIGKILL)
    else:
        print('\nVEREDICTO: el hijo muere con el master. El argumento de la')
        print('unidad separada NO puede apoyarse en el huerfano — hay que')
        print('rehacerlo sobre credenciales y reinicio independiente.')
    return 0


def pid_vivo(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


if __name__ == '__main__':
    sys.exit(main())
