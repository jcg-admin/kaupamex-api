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
Ver :ref:`h-api-854`.

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
