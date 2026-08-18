"""Configuración de Gunicorn — servidor de aplicación del producto L0 (ADR-027).

Adaptación de ``odoo19c: setup/odoo-wsgi.example.py`` (``odoo-tools@622ddc2a``),
que documenta servirse bajo Gunicorn y publica su configuración::

    #   $ gunicorn odoo.http:root --pythonpath . -c odoo-wsgi.py
    bind = '127.0.0.1:8069'
    pidfile = '.gunicorn.pid'
    workers = 4
    timeout = 240
    max_requests = 2000

Aquí la invocación equivalente es, desde la raíz del repositorio::

    $ gunicorn -c setup/gunicorn.conf.py

``wsgi_app`` y ``pythonpath`` van en este archivo (no en la línea de comandos)
para que la unidad systemd del paquete distribuible tenga un ``ExecStart`` sin
banderas — la misma forma que usa ``odoo19c: debian/odoo.service``.

Divergencias respecto de la referencia, declaradas
-----------------------------------------------------

1. **El puerto es 8000, no 8069.** 8069 es el puerto estándar *de Odoo*: copiarlo
   importaría la identidad de otro producto. 8000 es el que este proyecto ya usa
   — ``ui: webpack.config.js:280`` resuelve el backend a
   ``API_PROXY_TARGET || 'http://localhost:8000'``. Lo que sí se adopta de la
   referencia es la **forma**: enlazar sólo a loopback, de modo que el único
   proceso expuesto sea el front.
2. **Los valores se leen del entorno con los de la referencia como default.** El
   ejemplo de la referencia es una plantilla que el operador edita a mano; aquí
   la configuración del proyecto viaja por variables de entorno (``python-decouple``
   en ``config/settings``), y una unidad systemd las inyecta con
   ``EnvironmentFile``. Se usa ``os.environ`` directo, no ``decouple``, porque
   este archivo se ejecuta antes de que Django se cargue y no debe depender de
   encontrar un ``.env``.
3. **``max_requests_jitter`` se añade.** ``max_requests`` sin jitter hace que
   todos los workers reciclen casi a la vez; el jitter reparte el reinicio. La
   referencia no lo declara en su ejemplo.
"""

import multiprocessing
import os
import sys

# ── Raíz del código ──────────────────────────────────────────────────────────
# Se inserta aquí, en el cuerpo del archivo de configuración, y NO con la
# setting `pythonpath` de Gunicorn. Motivo medido (gunicorn 26.0.0,
# `app/base.py:205-233`): `--check-config` carga la aplicación en el bloque de
# arriba y `pythonpath` se aplica ~25 líneas más abajo, así que con la setting el
# gate falla con ModuleNotFoundError aunque el arranque real funcione. El
# archivo de configuración sí se ejecuta antes de ambos.
#
# Es además la forma de la referencia: su `odoo-wsgi.example.py` resuelve el
# import de la aplicación dentro del propio archivo de configuración
# (`from odoo.http import root as application`).
_SRC = os.path.abspath(os.environ.get('KAUPAMEX_SRC') or
                       os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def _int_env(name, default):
    """Lee un entero del entorno; ante un valor no numérico usa el default."""
    raw = os.environ.get(name, '')
    try:
        return int(raw)
    except ValueError:
        return default


# ── Dónde escucha ────────────────────────────────────────────────────────────
# Sólo loopback: el proceso expuesto es el proxy inverso, nunca la aplicación
# (CNST-ARQ-001 D2). Para servir directo, sin front, el operador fija
# GUNICORN_BIND='0.0.0.0:8000' — el producto no lo impide.
bind = os.environ.get('GUNICORN_BIND', '127.0.0.1:8000')

# ── Qué sirve ────────────────────────────────────────────────────────────────
# El punto de entrada no cambia con esta decisión: es el mismo objeto
# `application` que mod_wsgi cargaba vía WSGIScriptAlias.
wsgi_app = 'config.wsgi:application'

# ── Modelo de concurrencia ───────────────────────────────────────────────────
# Prefork síncrono — el mismo que mod_wsgi en modo demonio ya usaba. NO cambiar
# a un worker asíncrono sin un ADR: la aplicación es WSGI síncrona (0 `async def`
# medidos, ADR-027) y el driver de base tampoco es cooperativo: psycopg 3 en
# modo síncrono bloquea el hilo mientras espera a PostgreSQL (ADR-028).
#
# Decía «mysqlclient», que quedó atrás con la migración de motor (ADR-028,
# 2026-08-06). Corregido al leer este archivo como fuente del modelo de
# concurrencia en la tarea #535: un archivo que se cita como autoridad no puede
# nombrar un driver que el producto ya no usa.
workers = _int_env('GUNICORN_WORKERS', 4)
threads = _int_env('GUNICORN_THREADS', 1)

# ── Ciclo de vida del worker ─────────────────────────────────────────────────
timeout = _int_env('GUNICORN_TIMEOUT', 240)
graceful_timeout = _int_env('GUNICORN_GRACEFUL_TIMEOUT', 30)
max_requests = _int_env('GUNICORN_MAX_REQUESTS', 2000)
max_requests_jitter = _int_env('GUNICORN_MAX_REQUESTS_JITTER', 200)

# ── Proceso ──────────────────────────────────────────────────────────────────
pidfile = os.environ.get('GUNICORN_PIDFILE', '.gunicorn.pid')
proc_name = 'kaupamex-api'

# ── Detrás de un proxy inverso ───────────────────────────────────────────────
# El front DEBE fijar X-Forwarded-For / X-Real-IP / X-Forwarded-Proto /
# X-Forwarded-Host. Sin ellas la traza por dispositivo (res.device.log, cuya
# identidad es la terna plataforma/navegador/IP) registraría la IP del proxy en
# cada petición y colapsaría a una entrada por usuario.
#
# forwarded_allow_ips acota QUIÉN puede fijar esas cabeceras: el default de
# Gunicorn ('127.0.0.1') es correcto cuando el proxy corre en el mismo host.
# Ampliarlo a '*' aceptaría cabeceras falsificadas desde cualquier origen.
forwarded_allow_ips = os.environ.get('GUNICORN_FORWARDED_ALLOW_IPS', '127.0.0.1')

# ── Bitácora ─────────────────────────────────────────────────────────────────
# '-' = stdout/stderr, para que el supervisor (systemd/journald) sea el dueño de
# la bitácora. Es el mismo criterio que ADR-008 aplica al arranque: quién
# supervisa se declara por entorno, no se asume.
accesslog = os.environ.get('GUNICORN_ACCESSLOG', '-')
errorlog = os.environ.get('GUNICORN_ERRORLOG', '-')
loglevel = os.environ.get('GUNICORN_LOGLEVEL', 'info')

# Sugerencia de dimensionado para el operador; NO se aplica sola, porque la VM
# de producción está declarada saturada (ADR-027) y un default por CPU podría
# levantar más workers de los que la máquina soporta.
SUGERENCIA_WORKERS = 2 * multiprocessing.cpu_count() + 1
