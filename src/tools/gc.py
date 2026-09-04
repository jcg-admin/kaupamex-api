"""``tools.gc`` — instrumentación del recolector de basura de CPython.

Fiel a ``odoo19c: odoo/tools/gc.py`` (LGPL-3 — copia adaptada con atribución
preservada, DEC-KX-03).

Referencia del mecanismo que se instrumenta:
https://github.com/python/cpython/blob/main/InternalDocs/garbage_collector.md

Resumen de CPython, verbatim del razonamiento de la fuente: los objetos llevan
cuenta de referencias, pero hace falta recolección para los ciclos. Todo objeto
asignado cae en una colección (o *generación*); hay además una generación
permanente que nunca se recolecta (``gc.freeze``).

La recolección la dispara el **número de objetos creados**: en cada asignación
y liberación un contador sube y baja, y al llegar al umbral esa colección se
recolecta. Antes de 3.14, otros umbrales indican que cada X recolecciones se
recolecta la siguiente. Desde 3.14 sólo hay una colección adicional, que se
recolecta de forma incremental: se recolecta ``1 / threshold1`` por ciento del
montón.

Los tres consumidores medidos en la referencia son de ``disabling_gc``
(``odoo/orm/registry.py:113``, ``odoo/service/server.py:1511`` y
``odoo/tools/profiler.py:570``): el recolector se apaga durante la carga del
registro y durante el perfilado, donde su coste es medible y su beneficio nulo.
"""
import contextlib
import gc
import logging
from time import thread_time_ns as _gc_time

_logger = logging.getLogger('gc')
_gc_start: int = 0
_gc_init_stats = gc.get_stats()
_gc_timings = [0, 0, 0]


def _to_ms(ns):
    """Nanosegundos a milisegundos, con dos decimales."""
    return round(ns / 1_000_000, 2)


def _timing_gc_callback(event, info):
    """Se llama antes y después de cada pasada del gc — ver ``gc_set_timing``."""
    # Evitar llamar a los métodos de time si el módulo ya se descargó.
    if _gc_time is None:
        return
    global _gc_start  # noqa: PLW0603
    gen = info['generation']
    if event == 'start':
        _gc_start = _gc_time()
        # python 3.14: gen2 sólo se recolecta al llamar gc.collect() a mano.
        if gen == 2 and _logger.isEnabledFor(logging.DEBUG):
            _logger.debug("info %s, starting collection of gen2", gc_info())
    else:
        timing = _gc_time() - _gc_start
        _gc_timings[gen] += timing
        _gc_start = 0
        if gen > 0:
            _logger.debug("collected %s in %.2fms", info, _to_ms(timing))


def gc_set_timing(*, enable: bool):
    """Habilita o deshabilita el callback de medición.

    Recoge cuánto tiempo pasa el proceso dentro del recolector y registra
    (a nivel debug) las recolecciones de generación mayor que 0. El sobrecoste
    está por debajo del microsegundo.
    """
    if _timing_gc_callback in gc.callbacks:
        if enable:
            return
        gc.callbacks.remove(_timing_gc_callback)
    elif enable:
        global _gc_init_stats, _gc_timings  # noqa: PLW0603
        _gc_init_stats = gc.get_stats()
        _gc_timings = [0, 0, 0]
        gc.callbacks.append(_timing_gc_callback)


def gc_info():
    """Un diccionario con las estadísticas del recolector de basura."""
    stats = gc.get_stats()
    times = []
    cumulative_time = sum(_gc_timings) or 1
    for info, info_init, time in zip(stats, _gc_init_stats, _gc_timings):
        count = info['collections'] - info_init['collections']
        times.append({
            'avg_time': time // count if count > 0 else 0,
            'time': _to_ms(time),
            'pct': round(time / cumulative_time, 3),
        })
    return {
        'cumulative_time': _to_ms(cumulative_time),
        'time': times if _timing_gc_callback in gc.callbacks else (),
        'count': stats,
        'thresholds': (gc.get_count(), gc.get_threshold()),
    }


@contextlib.contextmanager
def disabling_gc():
    """Apaga el recolector dentro del contexto.

    Devuelve ``True`` si lo apagó y ``False`` si ya estaba apagado — quien
    llama puede así distinguir «lo apagué yo» de «ya venía apagado» sin
    volver a preguntarle a ``gc``.
    """
    if not gc.isenabled():
        yield False
        return
    gc.disable()
    _logger.debug('disabled, counts %s', gc.get_count())
    yield True
    counts = gc.get_count()
    gc.enable()
    _logger.debug('enabled, counts %s', counts)
