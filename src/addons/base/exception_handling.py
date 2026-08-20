"""``custom_exception_handler`` — el ``EXCEPTION_HANDLER`` de DRF (ADR-019).

Delega **primero** en el handler por defecto de DRF —el cuerpo de respuesta al
cliente NO cambia, conserva la clave canónica ``codigo_error``— y **después**
emite el error al canal de logging, que lo persiste como una fila de
``ir.logging`` (``IrLogging``, este mismo addon) vía ``DatabaseLogHandler``.

Por qué vive aquí, y por qué escribe a ``ir.logging``
=====================================================

Hasta DEC-AF-11 este archivo estaba en ``addons/observability`` y **sellaba**
el error en un ``ContextVar`` para que ``RequestLogMiddleware`` lo copiara a
una fila de ``RequestLog``. Esa decisión partió ``RequestLog`` en sus dos
mitades reales: la de **error** (``correlation_id``, ``path``,
``exception_class``, ``error_detail``) tiene contraparte en ``ir.logging``,
que ya está portado; la de **acceso** (``method``, ``status_code``,
``duration_ms``, ``ip``, ``user_agent``) no la tiene en el ORM de ningún árbol
y su hogar es el ``access_log`` del proxy inverso.

Con ``RequestLog`` retirado, el sellado en ``ContextVar`` perdía a su único
lector. Escribir aquí una fila de ``ir.logging`` a mano habría creado un
**segundo escritor** del mismo modelo, así que el error se emite por el canal
que ya existe: el logger ``django.request``, que ``LOGGING`` enruta al handler
``db`` (``tools.logging_handlers.DatabaseLogHandler``). Ese handler ya puebla
``correlation_id`` desde el contexto, ``path``/``func``/``line`` desde el
``LogRecord`` y ``trace`` desde ``exc_info``, todo con el scrubber de Nivel 1.

Dos consecuencias declaradas, no efectos colaterales
=====================================================

- **El nivel se deriva del estado HTTP.** ``>= 500`` → ``ERROR`` y con
  traceback (es un fallo del servidor); ``4xx`` → ``WARNING`` y sin traceback
  (es un error del cliente, y su pila no aporta). El sellado anterior no tenía
  nivel: ``RequestLog`` guardaba el error de cualquier estado en las mismas
  dos columnas.
- **La ventana de retención de un 4xx cambia.** Vivía 30 días en
  ``RequestLog``; como ``WARNING`` de ``ir.logging`` vive 90 (DEC-LOG-05,
  niveles altos). Es una consecuencia de fundir las dos tablas, y si la
  ventana resulta ancha se ajusta en DEC-LOG-05 — tarea **#616**.

- **PII-safe (DEC-LOG-03):** el detalle pasa por ``scrub`` **aquí**, en el
  origen, además del scrubbing que el handler aplica al mensaje. No es
  redundancia ociosa: el mensaje también viaja a ``console`` y ``file``, que
  no pasan por el handler de base de datos.
- **No bloqueante (DEC-LOG-04):** la emisión va en ``try/except`` que traga el
  error; si el logging falla, la respuesta al cliente NO se altera.
"""
import logging

from rest_framework.views import exception_handler as drf_exception_handler

from tools.log_scrubber import scrub

# ``django.request`` es el nombre canónico de Django para los errores de
# petición y propaga al logger ``django``, que ``LOGGING`` conecta a ``db``.
# Un logger con el nombre de este módulo (``addons.base.…``) NO cuelga de
# ninguno de los dos árboles configurados y su registro no llegaría a
# ``ir.logging``.
_logger = logging.getLogger('django.request')


def custom_exception_handler(exc, context):
    """Envuelve el handler de DRF y emite el error a ``ir.logging`` (ADR-019)."""
    response = drf_exception_handler(exc, context)
    try:
        _emit(exc, context, response)
    except Exception:
        # silent OK because DEC-LOG-04: emitir el error al log jamas debe
        # romper el manejo de la excepcion original ni la respuesta al cliente.
        pass
    return response


def _emit(exc, context, response):
    """Emite una línea por el canal de logging con los cuatro datos del error.

    ``response`` es ``None`` cuando DRF no sabe manejar la excepción; ése es
    el caso no controlado y se trata como 500 — con traceback.
    """
    status_code = getattr(response, 'status_code', None) or 500
    request = (context or {}).get('request')
    method = getattr(request, 'method', '') or ''
    # El ``path`` de la URL va en el mensaje: la columna ``path`` de
    # ``ir.logging`` es el archivo del sitio de la llamada (semántica de la
    # referencia), no la ruta HTTP.
    path = getattr(request, 'path', '') or ''
    is_server_error = status_code >= 500
    _logger.log(
        logging.ERROR if is_server_error else logging.WARNING,
        '%s %s -> %s %s: %s',
        method, path, status_code, type(exc).__name__, scrub(str(exc)),
        exc_info=exc if is_server_error else None,
    )
