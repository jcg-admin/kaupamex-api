"""Contrato de ``tools.gc`` — el medidor del recolector de basura.

Fuente: ``odoo19c: odoo/tools/gc.py``. La fuente no trae pruebas propias, así
que estos casos miden el contrato que sus tres consumidores usan: el callback
se registra una sola vez, ``gc_info`` distingue «medido» de «no medido», y
``disabling_gc`` dice si fue él quien apagó el recolector.

El caso de ``disabling_gc`` sobre un recolector **ya apagado** es el control
que puede fallar: si el gestor de contexto encendiera el recolector al salir,
apagaría la intención de quien lo había apagado antes. Un caso que sólo mirara
el camino feliz no distinguiría las dos implementaciones.
"""
import gc

from tools import gc as gc_tools
from tools.gc import _timing_gc_callback, _to_ms, disabling_gc, gc_info, gc_set_timing


def _timing_off():
    """Deja el callback fuera de ``gc.callbacks``, como estaba al importar."""
    gc_set_timing(enable=False)


def test_nanoseconds_become_milliseconds_with_two_decimals():
    assert _to_ms(0) == 0
    assert _to_ms(1_000_000) == 1
    assert _to_ms(1_234_567) == 1.23
    assert _to_ms(1_235_000) == 1.24


def test_enabling_the_timing_registers_the_callback_once():
    try:
        gc_set_timing(enable=True)
        assert gc.callbacks.count(_timing_gc_callback) == 1
        # Idempotente: habilitar de nuevo no duplica el callback ni reinicia
        # los contadores acumulados.
        gc_set_timing(enable=True)
        assert gc.callbacks.count(_timing_gc_callback) == 1
    finally:
        _timing_off()


def test_disabling_the_timing_removes_the_callback_and_is_idempotent():
    gc_set_timing(enable=True)
    gc_set_timing(enable=False)
    assert _timing_gc_callback not in gc.callbacks
    # Deshabilitar dos veces no revienta.
    gc_set_timing(enable=False)
    assert _timing_gc_callback not in gc.callbacks


def test_the_callback_accumulates_the_time_of_a_collection():
    # Se lee por el módulo, no por un nombre importado: ``gc_set_timing``
    # **reasigna** ``_gc_timings`` a una lista nueva, así que un nombre atado
    # en el import seguiría apuntando a la lista vieja y siempre daría cero.
    try:
        gc_set_timing(enable=True)
        gc.collect()
        accumulated = list(gc_tools._gc_timings)
    finally:
        _timing_off()
    # ``_gc_timings`` se reinicia al habilitar, así que la comparación válida
    # es contra cero: alguna generación tiene que haber acumulado tiempo.
    assert sum(accumulated) > 0
    assert len(accumulated) == 3


def test_the_report_declares_whether_it_measured_anything():
    # Sin callback registrado, ``time`` es la tupla vacía — el informe dice
    # «no medí», no «midió cero».
    _timing_off()
    unmeasured = gc_info()
    assert unmeasured['time'] == ()
    assert set(unmeasured) == {'cumulative_time', 'time', 'count', 'thresholds'}
    assert len(unmeasured['count']) == 3
    assert len(unmeasured['thresholds']) == 2

    try:
        gc_set_timing(enable=True)
        gc.collect()
        measured = gc_info()
    finally:
        _timing_off()
    assert isinstance(measured['time'], list)
    assert len(measured['time']) == 3
    for entry in measured['time']:
        assert set(entry) == {'avg_time', 'time', 'pct'}


def test_the_context_manager_reports_that_it_turned_the_collector_off():
    assert gc.isenabled()
    with disabling_gc() as turned_off:
        assert turned_off is True
        assert not gc.isenabled()
    assert gc.isenabled()


def test_the_context_manager_leaves_an_already_disabled_collector_alone():
    gc.disable()
    try:
        with disabling_gc() as turned_off:
            assert turned_off is False
            assert not gc.isenabled()
        # El control que discrimina: al salir sigue apagado. Encenderlo aquí
        # revertiría la decisión de quien lo apagó antes de entrar.
        assert not gc.isenabled()
    finally:
        gc.enable()
