"""
apps/core/logging_handlers.py

DatabaseLogHandler (SOL-011 T-03, DEC-LOG-02): un ``logging.Handler`` que
persiste cada ``LogRecord`` ruteado por ``LOGGING`` a la tabla ``AppLog``.
Adaptado del patron de django-db-logger 0.1.13 (MIT) sobre un modelo propio
PII-safe (DEC-LOG-06); no se instala el paquete.

Garantias:

- **PII-safe (DEC-LOG-03):** ``msg`` y ``trace`` pasan por el ``PIIScrubber`` de
  Nivel 1 antes de insertar (los tracebacks exponen ``locals`` con secretos).
- **Correlacion (DEC-LOG-07):** ``correlation_id`` se toma del contexto de la
  request; vacio fuera de un request.
- **No bloqueante (DEC-LOG-04):** un fallo al persistir NUNCA propaga al
  call-site (se absorbe).
- **Anti-recursion (DEC-LOG-04):** se excluye a ``django.db*`` (el INSERT de
  ``AppLog`` emite el SQL como log y reingresaria) y usa una guarda de
  reentrancia por hilo.

El modelo ``AppLog`` se resuelve con ``apps.get_model`` (una *llamada*, no un
``import`` de modulo) para no romper ``django.setup()``: este modulo se importa
al configurar ``LOGGING``, antes de que el registro de apps este poblado
(``no-lazy-imports`` excepcion analoga a la de ``AppConfig.ready``).
"""
import logging
import threading

from django.apps import apps as django_apps

from core.log_scrubber import scrub
from core.logging_context import get_correlation_id

_reentrancy = threading.local()
_exc_formatter = logging.Formatter()


class DatabaseLogHandler(logging.Handler):
    """Persiste cada record a ``AppLog``. Ver docstring del modulo."""

    def emit(self, record):
        # django.db* emite el SQL del propio INSERT -> loop infinito. Excluir.
        if record.name.startswith('django.db'):
            return
        if getattr(_reentrancy, 'active', False):
            return
        _reentrancy.active = True
        try:
            app_log = django_apps.get_model('core', 'AppLog')
            trace = ''
            if record.exc_info:
                trace = scrub(_exc_formatter.formatException(record.exc_info))
            app_log.objects.create(
                logger_name=(record.name or '')[:255],
                level=(record.levelname or '')[:20],
                msg=scrub(record.getMessage()) or '',
                trace=trace or '',
                correlation_id=get_correlation_id() or '',
            )
        except Exception:
            # silent OK because DEC-LOG-04: el logging es no-bloqueante. Un
            # fallo al escribir AppLog (DB caida, tabla ausente en un contexto
            # sin migrar, etc.) se absorbe: nunca rompe el flujo que emitio el
            # log.
            pass
        finally:
            _reentrancy.active = False
