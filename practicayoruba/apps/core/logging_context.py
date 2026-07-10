"""
apps/core/logging_context.py

correlation_id por request (DEC-LOG-07): un UUID que une las tres tablas de
logging (RequestLog + AppLog + BusinessEvent) para reconstruir "que paso" en
una request. Se expone via contextvars para que cualquier capa (handler de
logging, señales de negocio) lo lea sin propagarlo por parametro.
"""
import contextvars
import uuid

# Default None: fuera de un request (management commands, tests unitarios sin
# request) no hay correlacion — el consumidor debe tolerar None.
_correlation_id_var = contextvars.ContextVar("correlation_id", default=None)


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


def clear_correlation_id():
    """Limpia el correlation_id del contexto (fin del request)."""
    _correlation_id_var.set(None)
