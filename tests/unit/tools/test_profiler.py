"""Contrato de ``tools.profiler`` — colectores, contexto de ejecución y sesión.

Fuente: ``odoo19c: odoo/tools/profiler.py``. La referencia no trae pruebas de
este módulo; estos casos miden el comportamiento que sus consumidores usan —
``tools/speedscope.py`` y el modelo ``ir.profile``.

Los dos controles que discriminan, medidos con la guarda anulada
(``scripts/evidence/profiler-controles.log``):

* **La guarda del marco** de ``PeriodicCollector.add``
  (``if frame == self.last_frame: return``). Su comentario dice que salta el
  marco duplicado y **no es lo que el código hace**: el bloque de
  congelamiento limpia ``last_frame`` en cuanto había uno, así que la
  comparación nunca ve el marco anterior. Lo que la guarda sí atrapa es el
  hilo **sin marco**, donde ``frame`` resuelve a ``None``. Ver H-API-1079.
* **El salto de los marcos de este archivo** en ``get_current_frame``
  (``while frame.f_code.co_filename == __file__``). Sin él, la traza que se
  guarda empieza dentro del propio perfilador y no en el código perfilado.

Ambos se anulan en el propio archivo, se mide qué cae, y se restaura
verificando la identidad del archivo por ``sha256`` — no por ``git diff``, que
es ciego a un archivo sin seguir.
"""
import json
import logging
import re
import sys
import threading

import pytest
from django.conf import settings
from django.db import connections, DEFAULT_DB_ALIAS

from tools import profiler as profiler_module
from tools.profiler import (
    Collector,
    ExecutionContext,
    Nested,
    PeriodicCollector,
    Profiler,
    QwebCollector,
    QwebTracker,
    SQLCollector,
    SyncCollector,
    _BasePeriodicCollector,
    _format_frame,
    _format_stack,
    _get_stack_trace,
    force_hook,
    get_current_frame,
    make_session,
    real_cpu_time,
    real_datetime_now,
    real_time,
    stack_size,
)


@pytest.fixture
def profiler():
    """Un perfilador sin colectores y sin guardado, ya dentro del ``with``."""
    with Profiler(db=None, collectors=[], description='caso') as active:
        yield active


def attach(collector, profiler):
    """Cuelga un colector de un perfilador ya activo, como haría ``__init__``."""
    collector.profiler = profiler
    return collector


def _another_frame():
    """Devuelve un marco real distinto del del llamador."""
    return sys._getframe()


class TestFrameHelpers:
    """Las cuatro piezas que traducen un marco de Python a una tupla."""

    def test_a_frame_becomes_a_four_field_tuple(self):
        frame = sys._getframe()
        filename, lineno, name, line = _format_frame(frame)
        assert filename == __file__
        assert name == 'test_a_frame_becomes_a_four_field_tuple'
        assert isinstance(lineno, int)
        assert line == ''

    def test_the_stack_is_serialized_as_lists(self):
        stack = [_format_frame(sys._getframe())]
        assert _format_stack(stack) == [list(stack[0])]
        assert all(isinstance(frame, list) for frame in _format_stack(stack))

    def test_the_current_frame_skips_the_profiler_own_frames(self):
        # El control de esta guarda vive en TestGuardsNeutralized: aquí sólo se
        # afirma el contrato, que es que el marco devuelto es del LLAMADOR.
        assert get_current_frame().f_code.co_filename == __file__

    def test_the_frame_of_another_thread_is_reachable_by_ident(self):
        ready = threading.Event()
        keep_going = threading.Event()
        seen = {}

        def worker():
            ready.set()
            keep_going.wait(5)

        current = threading.Thread(target=worker)
        current.start()
        try:
            ready.wait(5)
            seen['frame'] = get_current_frame(current)
        finally:
            keep_going.set()
            current.join(5)
        assert seen['frame'] is not None

    def test_the_trace_stops_at_the_limit_frame(self):
        limit = sys._getframe()

        def nested():
            return _get_stack_trace(sys._getframe(), limit)

        trace = nested()
        # Sólo el marco de ``nested``: el límite es exclusivo.
        assert [frame[2] for frame in trace] == ['nested']

    def test_the_trace_without_limit_reaches_the_root(self):
        trace = _get_stack_trace(sys._getframe())
        assert len(trace) > 1
        assert trace[-1][2] == 'test_the_trace_without_limit_reaches_the_root'

    def test_a_limit_frame_that_is_not_in_the_stack_is_reported(self, caplog):
        # El nivel RUNBOT vale 25; caplog tiene que estar por debajo para verlo.
        foreign = _format_frame  # cualquier objeto que no sea un marco de la pila
        with caplog.at_level(logging.INFO, logger='tools.profiler'):
            trace = _get_stack_trace(sys._getframe(), foreign)
        assert trace  # la traza sale completa aunque el límite no aparezca
        assert 'Limit frame was not found' in caplog.text

    def test_the_stack_size_grows_with_nesting(self):
        base = stack_size()

        def first():
            return stack_size()

        assert first() == base + 1


class TestSession:
    """``make_session`` y los tres relojes sin parchear."""

    def test_the_session_carries_the_timestamp_and_the_name(self):
        session = make_session('carga')
        assert session.endswith(' carga')
        assert len(session.split(' ')) == 3  # fecha, hora, nombre

    def test_an_empty_name_leaves_a_trailing_space(self):
        assert make_session().endswith(' ')

    def test_the_three_clocks_are_the_unpatched_ones(self):
        # La fuente los captura al importar para que freezegun no los altere.
        assert real_time() > 0
        assert real_cpu_time() >= 0
        assert real_datetime_now().year >= 2024


class TestForceHook:
    """``force_hook`` dispara los enganches periódicos del hilo actual."""

    def test_it_calls_every_registered_hook(self):
        current = threading.current_thread()
        calls = []
        current.profile_hooks = [lambda: calls.append(1), lambda: calls.append(2)]
        try:
            force_hook()
        finally:
            del current.profile_hooks
        assert calls == [1, 2]

    def test_a_thread_without_hooks_is_a_no_op(self):
        assert not hasattr(threading.current_thread(), 'profile_hooks')
        force_hook()  # no levanta


class TestCollectorRegistry:
    """``__init_subclass__`` registra por nombre simbólico Y por nombre de clase."""

    @pytest.mark.parametrize('key, expected', [
        ('sql', SQLCollector),
        ('SQLCollector', SQLCollector),
        ('traces_async', PeriodicCollector),
        ('PeriodicCollector', PeriodicCollector),
        ('traces_sync', SyncCollector),
        ('qweb', QwebCollector),
    ])
    def test_both_keys_resolve_to_the_same_class(self, key, expected):
        assert Collector._registry[key] is expected
        assert isinstance(Collector.make(key), expected)

    def test_a_subclass_without_name_is_not_registered(self):
        before = dict(Collector._registry)

        class Anonymous(Collector):
            pass

        assert Collector._registry == before

    def test_the_base_store_mirrors_the_base_name(self):
        # ``_store = name`` en el cuerpo de la clase: ambos None. Ningún
        # colector de la fuente lo redefine — es un enganche para subclases.
        assert Collector._store is None
        assert Collector.name is None


class TestCollectorEntries:
    """El ciclo ``add`` → ``progress`` → ``entries`` de la clase base."""

    def test_an_entry_carries_stack_context_and_start(self, profiler):
        collector = attach(Collector(), profiler)
        sample = collector.add()
        assert set(sample) == {'stack', 'exec_context', 'start'}
        assert sample['start'] > 0

    def test_the_given_entry_overrides_the_defaults(self, profiler):
        collector = attach(Collector(), profiler)
        sample = collector.add({'start': 42, 'query': 'SELECT 1'})
        assert sample['start'] == 42
        assert sample['query'] == 'SELECT 1'

    def test_entries_freeze_after_the_first_read(self, profiler):
        collector = attach(Collector(), profiler)
        collector.add()
        assert len(collector.entries) == 1
        assert collector._entries is None  # ya no se puede modificar
        assert collector.entries is collector.processed_entries

    def test_the_entry_count_limit_ends_the_profiler(self):
        with Profiler(db=None, collectors=[], params={'entry_count_limit': 2}) as active:
            collector = attach(Collector(), active)
            collector.progress()
            collector.progress()
            assert not active.done
            collector.progress()   # el tercero cruza el límite
            assert active.done

    def test_the_time_limit_ends_the_profiler(self):
        with Profiler(db=None, collectors=[], params={'time_limit': 1}) as active:
            collector = attach(Collector(), active)
            active.start_time = real_time() - 10   # el límite ya se pasó
            collector.progress()
            assert active.done

    def test_without_limits_the_profiler_stays_open(self, profiler):
        collector = attach(Collector(), profiler)
        for _ in range(5):
            collector.progress()
        assert not profiler.done
        assert profiler.counter == 5

    def test_the_summary_names_the_collector_and_counts(self, profiler):
        collector = attach(SQLCollector(), profiler)
        collector._entries = [{'time': 1, 'full_query': 'SELECT 1'}]
        assert 'sql' in collector.summary()
        assert 'SELECT 1' in collector.summary()


class TestExecutionContext:
    """El contexto que el colector guarda junto a la pila."""

    def test_it_stacks_and_restores(self):
        current = threading.current_thread()
        assert getattr(current, 'exec_context', ()) == ()
        with ExecutionContext(xpath='/t[1]'):
            (_, context), = current.exec_context
            assert context == {'xpath': '/t[1]'}
            with ExecutionContext(xpath='/t[2]'):
                assert len(current.exec_context) == 2
            assert len(current.exec_context) == 1
        assert current.exec_context == ()

    def test_the_stack_depth_is_recorded_with_the_context(self):
        current = threading.current_thread()
        with ExecutionContext(marca=1):
            (depth, _), = current.exec_context
            assert depth > 0

    def test_the_collector_copies_the_context_into_the_entry(self, profiler):
        collector = attach(Collector(), profiler)
        with ExecutionContext(directiva='t-if'):
            sample = collector.add()
        assert sample['exec_context'][0][1] == {'directiva': 't-if'}


class TestSQLCollector:
    """El enganche de consulta: se instala en el hilo y rinde el retardo."""

    class _Cursor:
        """Cursor mínimo: sólo lo que el enganche consume."""

        def mogrify(self, query, params):
            return query % tuple(repr(p) for p in params)

    def test_start_installs_the_hook_and_stop_removes_it(self, profiler):
        collector = attach(SQLCollector(), profiler)
        collector.start()
        try:
            assert collector.hook in profiler.init_thread.query_hooks
        finally:
            collector.stop()
        assert collector.hook not in profiler.init_thread.query_hooks

    def test_the_hook_records_the_query_and_yields_an_updater(self, profiler):
        collector = attach(SQLCollector(), profiler)
        update = collector.hook(
            self._Cursor(), 'SELECT %s', (7,), 1000.0, 0.5,
        )
        entry, = collector._entries
        assert entry['query'] == 'SELECT %s'
        assert entry['full_query'] == "SELECT 7"
        assert entry['start'] == 1000.0
        assert entry['time'] == 0.5
        update(2.5)
        assert entry['time'] == 2.5   # el retardo real llega después

    def test_the_summary_weights_each_query_against_the_total(self, profiler):
        collector = attach(SQLCollector(), profiler)
        collector._entries = [
            {'time': 1.0, 'full_query': 'SELECT a'},
            {'time': 3.0, 'full_query': 'SELECT b'},
        ]
        summary = collector.summary()
        # ``str.count`` de una racha de 25 cuenta 3 veces dentro de una de 75:
        # la longitud se mide sobre la racha entera, no contando subcadenas.
        runs = [len(run) for run in re.findall(r'\*+', summary)]
        assert runs == [25, 75]   # 1/4 y 3/4 del total


class TestPeriodicCollector:
    """El muestreador asíncrono y sus dos guardas."""

    @pytest.mark.parametrize('declared, wanted', [
        ('99', _BasePeriodicCollector._max_interval),
        ('0.0000001', _BasePeriodicCollector._min_interval),
    ])
    def test_the_interval_is_clamped_between_the_declared_bounds(self, declared, wanted):
        # ``params`` viaja por el constructor y no asignándolo al perfilador ya
        # abierto: ``__enter__`` es quien lo cuelga del hilo y ``end`` quien lo
        # descuelga, así que asignarlo después deja el ``del`` sin objeto.
        with Profiler(db=None, collectors=[],
                      params={'traces_async_interval': declared}) as active_profiler:
            collector = attach(PeriodicCollector(), active_profiler)
            collector.start()
            try:
                assert collector.frame_interval == wanted
            finally:
                collector.stop()

    def test_stop_appends_the_final_empty_frame(self, profiler):
        collector = attach(PeriodicCollector(), profiler)
        profiler.params = {}
        collector.start()
        collector.stop()
        assert collector._entries[-1]['stack'] == []
        assert collector.progress not in profiler.init_thread.profile_hooks

    def test_the_same_frame_twice_is_still_recorded_twice(self, profiler):
        # El comentario de la fuente dice «no se guarda si el marco es
        # exactamente el mismo que el anterior», y el código NO hace eso: el
        # bloque de congelamiento pone ``last_frame = None`` en cuanto había
        # uno, así que la comparación siguiente nunca ve el marco anterior.
        # Medido aquí, no leído del comentario. Ver H-API-1079.
        collector = attach(PeriodicCollector(), profiler)
        collector._memory_profile = False
        own_frame = sys._getframe()
        collector.add(frame=own_frame)
        collector.add(frame=own_frame)
        assert len(collector._entries) == 2

    def test_the_frame_guard_fires_when_the_thread_has_no_frame(self, monkeypatch):
        # La guarda que sí discrimina: con ``last_frame`` limpio y el hilo sin
        # marco, ``frame`` resuelve a ``None`` y la entrada no se guarda. Sin
        # la guarda, ``_get_stack_trace(None)`` daría una pila vacía y una
        # entrada falsa por cada muestra.
        with Profiler(db=None, collectors=[], description='sin marco') as active_profiler:
            collector = attach(PeriodicCollector(), active_profiler)
            collector._memory_profile = False
            monkeypatch.setattr(profiler_module, 'get_current_frame', lambda thread=None: None)
            collector.add()
            assert collector._entries == []

    def test_a_long_sleep_marks_the_freeze(self, profiler):
        collector = attach(PeriodicCollector(), profiler)
        collector._memory_profile = False
        collector.frame_interval = 0.001
        collector.add(frame=sys._getframe())
        collector._last_time = real_time() - 10   # durmió 10 s con intervalo de 1 ms
        collector.add(frame=_another_frame())
        marker = collector._entries[0]['stack'][-1]
        assert marker[0] == 'profiling'
        assert 'Profiler freezed' in marker[2]

    def test_the_memory_profile_adds_the_rss(self, profiler):
        collector = attach(PeriodicCollector(), profiler)
        collector._memory_profile = True
        collector._process = profiler.process
        collector.add(frame=sys._getframe())
        assert collector._entries[0]['memory'] > 0


class TestSyncCollector:
    """El trazador síncrono: guarda eventos y recompone la pila al final."""

    def test_the_line_event_is_ignored(self, profiler):
        collector = attach(SyncCollector(), profiler)
        assert collector.hook(sys._getframe(), 'line') is None
        assert collector._entries == []

    def test_a_call_records_the_parent_frame(self, profiler):
        collector = attach(SyncCollector(), profiler)
        collector.hook(sys._getframe(), 'call')
        entry, = collector._entries
        assert entry['event'] == 'call'
        assert 'parent_frame' in entry

    def test_the_sync_collector_does_not_walk_the_stack(self, profiler):
        collector = attach(SyncCollector(), profiler)
        assert collector._get_stack_trace() is None

    def test_the_evented_trace_becomes_full_stacks(self, profiler):
        collector = attach(SyncCollector(), profiler)
        parent = ('a.py', 1, 'main', '')
        parent_in_call = ('a.py', 2, 'main', '')
        child = ('a.py', 10, 'child', '')
        collector._entries = [
            {'event': 'call', 'frame': parent, 'parent_frame': parent},
            {'event': 'call', 'frame': child, 'parent_frame': parent_in_call},
            {'event': 'return', 'frame': child},
        ]
        collector.post_process()
        stacks = [entry['stack'] for entry in collector._entries]
        assert stacks[0] == [parent]
        # el marco del padre se reemplaza por el que trae la LÍNEA de la llamada
        assert stacks[1] == [parent_in_call, child]
        assert stacks[2] == [parent_in_call]

    def test_stop_clears_the_trace_function(self, profiler):
        collector = attach(SyncCollector(), profiler)
        collector.stop()
        assert sys.gettrace() is None


class TestQweb:
    """El rastreador de plantillas y su colector."""

    class _Cursor:
        sql_log_count = 0

    @pytest.mark.parametrize('directive, attrib, expected', [
        ('set', {'t-set': 'a', 't-value': '1'}, "t-set='a' t-value='1'"),
        ('set', {'t-set': 'a', 't-valuef': 'x'}, "t-set='a' t-valuef='x'"),
        ('set', {'t-set-b': '2'}, "t-set-b='2'"),
        ('foreach', {'t-foreach': 'xs', 't-as': 'x'}, "t-foreach='xs' t-as='x'"),
        ('options', {'t-options': 'o'}, "t-options='o'"),
        ('att', {'t-att-class': 'c'}, "t-att-class='c'"),
        ('if', {'t-if': 'cond'}, "t-if='cond'"),
        ('call', {}, 't-call'),
    ])
    def test_each_directive_family_has_its_own_label(self, directive, attrib, expected):
        collector = QwebCollector()
        assert collector._get_directive_profiling_name(directive, attrib) == expected

    def test_the_tracker_announces_the_render_to_every_hook(self):
        current = threading.current_thread()
        events = []
        current.qweb_hooks = [lambda event, count, **kw: events.append((event, kw))]
        try:
            QwebTracker(7, '<t/>', self._Cursor())
        finally:
            del current.qweb_hooks
        assert events[0][0] == 'render'
        assert events[0][1] == {'view_id': 7, 'arch': '<t/>'}

    def test_enter_and_leave_reach_the_hooks(self):
        current = threading.current_thread()
        events = []
        current.qweb_hooks = [lambda event, count, **kw: events.append(event)]
        try:
            tracker = QwebTracker(7, '<t/>', self._Cursor())
            tracker.enter_directive('if', {'t-if': 'x'}, '/t[1]')
            tracker.leave_directive('if', {'t-if': 'x'}, '/t[1]')
        finally:
            del current.qweb_hooks
        assert events == ['render', 'enter', 'leave']

    def test_the_execution_context_is_pushed_only_when_enabled(self):
        current = threading.current_thread()
        current.qweb_hooks = []
        current.profiler_params = {'execution_context_qweb': True}
        try:
            tracker = QwebTracker(7, '<t/>', self._Cursor())
            tracker.enter_directive('if', {'t-if': 'x'}, '/t[1]')
            assert len(current.exec_context) == 1
            tracker.leave_directive('if', {'t-if': 'x'}, '/t[1]')
            assert current.exec_context == ()
        finally:
            del current.qweb_hooks
            del current.profiler_params

    def test_the_post_process_accumulates_delay_and_queries(self, profiler):
        collector = attach(QwebCollector(), profiler)
        collector.events = [
            ('render', {'view_id': 1, 'arch': '<t/>'}, 0, 0.0),
            ('enter', {'view_id': 1, 'xpath': '/t[1]', 'directive': 'if',
                       'attrib': {'t-if': 'x'}}, 0, 1.0),
            ('leave', {'view_id': 1, 'xpath': '/t[1]', 'directive': 'if',
                       'attrib': {'t-if': 'x'}}, 3, 1.5),
        ]
        collector.post_process()
        results = collector._entries[0]['results']
        assert results['archs'] == {1: '<t/>'}
        item, = results['data']
        assert item['directive'] == "t-if='x'"
        assert item['delay'] == pytest.approx(0.5)
        assert item['query'] == 3


class TestProfiler:
    """El gestor de contexto: descripción, límites, salida y anidamiento."""

    def test_the_description_defaults_to_the_calling_frame(self):
        with Profiler(db=None, collectors=[]) as active:
            assert 'test_the_description_defaults_to_the_calling_frame' in active.description
            assert __file__ in active.description

    def test_the_default_collectors_are_sql_and_traces_async(self):
        standalone = Profiler(db=None)
        assert [collector.name for collector in standalone.collectors] == ['sql', 'traces_async']

    def test_an_unknown_collector_is_reported_and_skipped(self, caplog):
        with caplog.at_level(logging.ERROR, logger='tools.profiler'):
            standalone = Profiler(db=None, collectors=['inexistente', 'sql'])
        assert [collector.name for collector in standalone.collectors] == ['sql']
        assert 'Could not create collector' in caplog.text

    def test_an_unconfigured_alias_is_refused(self):
        # La guarda que la fuente expresa como excepción: aquí PUEDE fallar,
        # y por eso el caso vale.
        assert 'no_existe' not in settings.DATABASES
        with pytest.raises(ValueError, match='no_existe'):
            Profiler(db='no_existe', collectors=[])

    def test_the_thread_dbname_wins_over_the_default_alias(self):
        current = threading.current_thread()
        current.dbname = DEFAULT_DB_ALIAS
        try:
            assert Profiler(collectors=[]).db == DEFAULT_DB_ALIAS
        finally:
            del current.dbname

    def test_the_params_live_on_the_thread_only_inside_the_with(self):
        current = threading.current_thread()
        with Profiler(db=None, collectors=[], params={'k': 'v'}):
            assert current.profiler_params == {'k': 'v'}
        assert not hasattr(current, 'profiler_params')

    def test_end_is_idempotent(self, profiler):
        profiler.end()
        assert profiler.done
        profiler.end()   # no levanta ni recalcula
        assert profiler.done

    def test_the_duration_and_the_cpu_duration_are_measured(self):
        with Profiler(db=None, collectors=[]) as active:
            sum(range(100000))
        assert active.duration > 0
        assert active.cpu_duration > 0

    def test_the_entry_count_adds_up_every_collector(self, profiler):
        first = attach(Collector(), profiler)
        other = attach(Collector(), profiler)
        profiler.collectors = [first, other]
        first.add()
        other.add()
        other.add()
        assert profiler.entry_count() == 3

    def test_the_path_is_formatted_with_time_len_and_desc(self, profiler):
        path = profiler.format_path('/tmp/{desc}_{len}_{time}.json')
        assert path.startswith('/tmp/caso_0_')
        assert path.endswith('.json')

    def test_a_description_with_symbols_is_sanitized_in_the_path(self):
        with Profiler(db=None, collectors=[], description='GET /api/v2/x') as active:
            assert active.format_path('{desc}') == 'GET_api_v2_x'

    def test_the_json_carries_the_six_declared_keys(self, profiler):
        data = json.loads(profiler.json())
        assert set(data) == {
            'name', 'session', 'create_date', 'init_stack_trace',
            'duration', 'collectors',
        }
        assert data['name'] == 'caso'

    def test_the_summary_walks_the_sub_profilers(self, profiler):
        inner_profiler = Profiler(db=None, collectors=[], description='interno')
        inner_profiler.collectors = [attach(SQLCollector(), inner_profiler)]
        profiler.sub_profilers = [inner_profiler]
        assert 'sql' in profiler.summary()

    def test_the_file_lines_are_filled_from_the_cache(self, profiler):
        one_stack = [(__file__, 1, 'x', ''), (__file__, 1, 'y', '')]
        profiler._add_file_lines(one_stack)
        # Se lea o no (``file_open`` confina las rutas), la caché se consulta
        # una sola vez por archivo.
        assert list(profiler.filecache) == [__file__]

    def test_a_frame_without_lineno_is_left_alone(self, profiler):
        one_stack = [('<decorator>', 0, 'x', '')]
        profiler._add_file_lines(one_stack)
        assert one_stack == [('<decorator>', 0, 'x', '')]
        assert profiler.filecache == {}

    def test_a_frame_that_already_has_its_line_is_left_alone(self, profiler):
        one_stack = [(__file__, 1, 'x', 'ya la trae\n')]
        profiler._add_file_lines(one_stack)
        assert one_stack[0][3] == 'ya la trae\n'
        assert profiler.filecache == {}


class TestNested:
    """El proxy que permite anidar otro gestor de contexto."""

    def test_it_enters_and_exits_both(self):
        trace = []

        class Inner:
            def __enter__(self):
                trace.append('enter')
                return 'valor'

            def __exit__(self, *args):
                trace.append('exit')
                return False

        standalone = Profiler(db=None, collectors=[], description='anidado')
        with Nested(standalone, Inner()) as value:
            assert value == 'valor'
            assert not standalone.done
        assert trace == ['enter', 'exit']
        assert standalone.done

    def test_the_proxy_defaults_to_a_null_context(self):
        standalone = Profiler(db=None, collectors=[], description='anidado')
        with standalone._get_cm_proxy():
            pass
        assert standalone.done

    def test_the_profiler_closes_even_if_the_inner_raises(self):
        class Boom:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                raise RuntimeError('interno')

        standalone = Profiler(db=None, collectors=[], description='anidado')
        with pytest.raises(RuntimeError, match='interno'):
            with Nested(standalone, Boom()):
                pass
        assert standalone.done


@pytest.mark.django_db
class TestProfilerPersistence:
    """El guardado en ``ir_profile`` por una conexión aparte."""

    def test_the_profile_lands_in_ir_profile(self):
        with Profiler(collectors=['sql'], description='persistido') as active:
            pass
        assert active.profile_id is not None
        separate = connections.create_connection(DEFAULT_DB_ALIAS)
        try:
            with separate.cursor() as cursor:
                cursor.execute(
                    'SELECT name, session, entry_count, sql_count FROM ir_profile WHERE id = %s',
                    (active.profile_id,),
                )
                row_name, session, entries, queries = cursor.fetchone()
                assert row_name == 'persistido'
                assert session == active.profile_session
                assert entries == 0 and queries == 0
                # La fila la escribió OTRA conexión: no la revierte el rollback
                # del caso. Se limpia aquí, por el mismo camino.
                cursor.execute('DELETE FROM ir_profile WHERE id = %s', (active.profile_id,))
            separate.commit()
        finally:
            separate.close()

    def test_a_falsy_db_skips_the_write(self):
        with Profiler(db=None, collectors=[]) as active:
            pass
        assert active.profile_id is None
