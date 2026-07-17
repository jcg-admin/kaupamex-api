"""
apps/core/exception_handling.py

custom_exception_handler (SOL-011 T-04, ADR-019): el ``EXCEPTION_HANDLER`` de DRF
del proyecto. Delega **primero** en el handler por defecto de DRF (el cuerpo de
respuesta al cliente NO cambia — conserva la clave canonica ``codigo_error``,
351 usos) y **despues** sella ``exception_class`` / ``error_detail`` (scrubbed,
Nivel 1) en el contexto de la request para que el ``RequestLogMiddleware`` los
persista en su fila ``RequestLog`` (unida al trace de ``AppLog`` por
``correlation_id``, DEC-LOG-07).

- **PII-safe (DEC-LOG-03):** ``error_detail`` pasa por el scrubber. NO es el
  traceback completo (ese va a ``AppLog.trace`` via ``django.request`` +
  ``DatabaseLogHandler``); aqui solo el mensaje corto.
- **No bloqueante (DEC-LOG-04):** el sellado va en ``try/except`` que traga el
  error; si el logging falla, la respuesta de error al cliente NO se altera.
"""
from rest_framework.views import exception_handler as drf_exception_handler

from core.log_scrubber import scrub
from core.logging_context import set_request_error


def custom_exception_handler(exc, context):
    """Envuelve el handler de DRF y sella el error en el contexto (ADR-019)."""
    response = drf_exception_handler(exc, context)
    try:
        set_request_error(type(exc).__name__, scrub(str(exc)))
    except Exception:
        # silent OK because DEC-LOG-04: sellar el error en el log jamas debe
        # romper el manejo de la excepcion original ni la respuesta al cliente.
        pass
    return response
