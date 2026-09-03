"""
tools/logging_handlers.py

DatabaseLogHandler (SOL-011 T-03, DEC-LOG-02): un ``logging.Handler`` que
persiste cada ``LogRecord`` ruteado por ``LOGGING`` al modelo fiel
``IrLogging`` (``ir.logging``, ``addons.base`` — DEC-08, slice 2). Adaptado del
patron de django-db-logger 0.1.13 (MIT) sobre un modelo propio PII-safe
(DEC-LOG-06); no se instala el paquete.

Movido desde ``core.logging_handlers`` en el slice 5 de
``adoptar-arquitectura-server-service-odoo`` (DEC-10).

**Corregido: el sitio NO es el de la referencia, y su contraparte existe.**
Esta linea decia *"fiel a Odoo la ubica en ``tools/``"*. Medido 2026-08-28:
la referencia declara este mismo mecanismo —un ``logging.Handler`` que
persiste el ``LogRecord`` en la base— como ``PostgreSQLHandler`` en
``odoo19c: odoo/netsvc.py:47``, con el docstring *"PostgreSQL Logging Handler
will store logs in the database"*. ``odoo/tools/`` no tiene ningun handler de
logging.

``netsvc.py`` es un modulo **top-level** de la referencia, no un archivo de
``odoo/tools/``, asi que el gate ``check_mirrored_roots.py`` —que compara raiz
contra raiz— es estructuralmente ciego a este par: nuestro archivo figura
*sin contraparte* cuando si la tiene. El veredicto sobre si se mueve a un
``src/netsvc.py`` es decision del ejecutor (tiene costo de imports); la
divergencia queda declarada aqui y en ``scripts/mirrored_roots_baseline.txt``.
Ver :ref:`h-api-855`.

Garantias:

- **PII-safe (DEC-LOG-03):** ``message`` y ``trace`` pasan por el
  ``PIIScrubber`` de Nivel 1 antes de insertar (los tracebacks exponen
  ``locals`` con secretos).
- **Correlacion (DEC-LOG-07):** ``correlation_id`` se toma del contexto de la
  request; vacio fuera de un request.
- **No bloqueante (DEC-LOG-04):** un fallo al persistir NUNCA propaga al
  call-site (se absorbe).
- **Anti-recursion (DEC-LOG-04):** se excluye a ``django.db*`` (el INSERT de
  ``IrLogging`` emite el SQL como log y reingresaria) y usa una guarda de
  reentrancia por hilo.
- **Call-site (path/func/line, fiel a Odoo):** se pueblan desde el propio
  ``LogRecord`` (``pathname``/``funcName``/``lineno``) cuando estan
  disponibles — el modelo previo (``AppLog``) no los capturaba.

El modelo ``IrLogging`` se resuelve con ``apps.get_model`` (una *llamada*, no un
``import`` de modulo) para no romper ``django.setup()``: este modulo se importa
al configurar ``LOGGING``, antes de que el registro de apps este poblado
(``no-lazy-imports`` excepcion analoga a la de ``AppConfig.ready``).
"""
import logging
import threading

from django.apps import apps as django_apps
from django.db import connection

from tools.log_scrubber import scrub
from tools.logging_context import get_correlation_id

_reentrancy = threading.local()
_exc_formatter = logging.Formatter()

#: Nivel ``RUNBOT`` — ``odoo19c: odoo/netsvc.py:339``. Se sitúa entre ``INFO``
#: (20) y ``WARNING`` (30): marca un mensaje dirigido a la infraestructura de
#: pruebas, no al operador. La referencia lo declara con su nombre propio y a
#: la vez lo mapea a ``"INFO"`` en ``_levelToName`` para que salga como INFO en
#: el log (``odoo19c: odoo/netsvc.py:340-341``).
RUNBOT = 25


def install_runbot_level():
    """Instala el nivel ``RUNBOT`` y el método ``Logger.runbot``.

    ≙ ``odoo19c: odoo/netsvc.py:339-341,365-367``, donde las cinco líneas se
    ejecutan al importar el módulo. Aquí van en una función **idempotente** que
    su consumidor llama explícitamente: un import cuyo único efecto es un
    side-effect no se distingue de un import muerto, y el gate de imports no
    puede protegerlo.

    El sitio es ``tools/logging_handlers.py`` y no ``src/netsvc.py`` por la
    misma razón que ``DatabaseLogHandler`` (ver el docstring del módulo): éste
    es el hogar declarado de las piezas de logging de ``netsvc`` en este árbol,
    y la divergencia de sitio ya está registrada en :ref:`h-api-855`.
    """
    logging.RUNBOT = RUNBOT
    logging.addLevelName(RUNBOT, "RUNBOT")
    # Se muestra como INFO en el log, igual que en la referencia.
    logging._levelToName[RUNBOT] = "INFO"

    def runbot(self, message, *args, **kws):
        self.log(RUNBOT, message, *args, **kws)

    logging.Logger.runbot = runbot


class DatabaseLogHandler(logging.Handler):
    """Persiste cada record a ``IrLogging``. Ver docstring del modulo."""

    def emit(self, record):
        # django.db* emite el SQL del propio INSERT -> loop infinito. Excluir.
        if record.name.startswith('django.db'):
            return
        if getattr(_reentrancy, 'active', False):
            return
        _reentrancy.active = True
        try:
            ir_logging = django_apps.get_model('base', 'IrLogging')
            trace = ''
            if record.exc_info:
                trace = scrub(_exc_formatter.formatException(record.exc_info))
            try:
                dbname = connection.settings_dict.get('NAME', '') or ''
            except Exception:
                dbname = ''
            ir_logging.objects.create(
                name=(record.name or '')[:255],
                type=ir_logging.TYPE_SERVER,
                dbname=str(dbname)[:255],
                level=(record.levelname or '')[:20],
                message=scrub(record.getMessage()) or '',
                path=(getattr(record, 'pathname', '') or '')[:255],
                func=(getattr(record, 'funcName', '') or '')[:255],
                line=str(getattr(record, 'lineno', '') or ''),
                trace=trace or '',
                correlation_id=get_correlation_id() or '',
            )
        except Exception:
            # silent OK because DEC-LOG-04: el logging es no-bloqueante. Un
            # fallo al escribir IrLogging (DB caida, tabla ausente en un
            # contexto sin migrar, etc.) se absorbe: nunca rompe el flujo que
            # emitio el log.
            pass
        finally:
            _reentrancy.active = False
