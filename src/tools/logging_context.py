"""
tools/logging_context.py

correlation_id por request (DEC-LOG-07): un UUID que une las dos tablas de
logging (IrLogging + BusinessEvent) para reconstruir "que paso" en una request.
Se expone via contextvars para que cualquier capa (handler de logging, señales
de negocio) lo lea sin propagarlo por parametro.

Movido desde ``core.logging_context`` en el slice 5 de
``adoptar-arquitectura-server-service-odoo`` (DEC-10).

**Corregido: la referencia no ubica esto en ninguna parte.** Esta linea decia
*"fiel a Odoo la ubica en ``tools/``"*, y eso describia un sitio que nadie
midio. Medido 2026-08-28: **0** ``ContextVar`` en el camino de logging de la
referencia (``odoo/netsvc.py``, ``odoo/logging.py``, ``odoo/http.py``). El
correlation_id por request es mecanismo **propio** de esta plataforma, no un
porte — su sitio lo elegimos nosotros, y ``tools/`` es una eleccion valida
mientras se declare como tal. Ver :ref:`h-api-854`.

**El error de la request ya no se sella aqui (DEC-AF-11).** Este modulo
declaraba ademas ``set_request_error``/``get_request_error``: el
``custom_exception_handler`` de DRF sellaba el error en un ContextVar y el
``RequestLogMiddleware`` lo copiaba a la fila ``RequestLog``. Retirado
``RequestLog``, ese ContextVar se quedo sin ningun lector, y un contextvar que
nadie lee es un mecanismo muerto. Hoy el handler emite el error por el canal de
logging y ``DatabaseLogHandler`` lo persiste en ``ir.logging`` — ver
``addons/base/exception_handling.py``.
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
    """Limpia la correlacion al terminar la request (DEC-LOG-07).

    Imprescindible bajo el modelo de concurrencia medido en
    ``setup/gunicorn.conf.py`` (prefork sincrono, un hilo por worker): sin esta
    limpieza el identificador sobreviviria a la peticion dentro del mismo
    worker y las lineas de la siguiente saldrian correlacionadas con la
    anterior.
    """
    _correlation_id_var.set(None)
