"""
apps/core/logging_context.py

correlation_id por request (DEC-LOG-07): un UUID que une las tres tablas de
logging (RequestLog + IrLogging + BusinessEvent) para reconstruir "que paso" en
una request. Se expone via contextvars para que cualquier capa (handler de
logging, señales de negocio) lo lea sin propagarlo por parametro.
"""
import contextvars
import uuid

# Default None: fuera de un request (management commands, tests unitarios sin
# request) no hay correlacion — el consumidor debe tolerar None.
_correlation_id_var = contextvars.ContextVar("correlation_id", default=None)

# Error de la request en curso (SOL-011 T-04, ADR-019): el
# ``custom_exception_handler`` de DRF lo fija (clase de excepcion + detalle ya
# scrubbed) y el ``RequestLogMiddleware`` lo lee al construir la fila RequestLog.
# Va por contextvar (simetrico con correlation_id) para no acoplar el handler al
# objeto request. Default None: la mayoria de requests no tienen error.
_request_error_var = contextvars.ContextVar("request_error", default=None)


def new_correlation_id():
    """Genera un correlation_id (UUID4 en hex, 32 chars) y lo fija en el contexto."""
    cid = uuid.uuid4().hex
    _correlation_id_var.set(cid)
    return cid


def set_correlation_id(cid):
    """Fija un correlation_id explicito en el contexto actual."""
    _correlation_id_var.set(cid)


def get_correlation_id():
    """Devuelve el correlation_id del contexto actual, o None si no hay request."""
    return _correlation_id_var.get()


def set_request_error(exception_class, error_detail):
    """Registra el error de la request en curso (ADR-019).

    ``exception_class`` = nombre de la clase de excepcion; ``error_detail`` = un
    mensaje corto **ya scrubbed** (Nivel 1). Lo consume el RequestLogMiddleware.
    """
    _request_error_var.set({
        'exception_class': exception_class or '',
        'error_detail': error_detail or '',
    })


def get_request_error():
    """Devuelve el dict de error de la request, o None si no hubo excepcion."""
    return _request_error_var.get()


def clear_correlation_id():
    """Limpia el contexto de logging de la request (fin del request): tanto el
    ``correlation_id`` como el error registrado (ADR-019)."""
    _correlation_id_var.set(None)
    _request_error_var.set(None)
