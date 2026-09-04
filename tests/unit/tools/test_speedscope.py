"""Contrato de ``tools.speedscope`` — el formato de archivo del visor.

Fuente: ``odoo19c: odoo/tools/speedscope.py``. La fuente no trae pruebas
propias, así que estos casos miden los contratos que el visor consume: la
tabla compartida de marcos, el emparejamiento por prefijo común, y las tres
variantes de salida (tiempo, densidad y memoria).

Cuatro controles pueden fallar y son los que dan valor a la suite:

* el **prefijo común** se mide con dos entradas cuya pila comparte el marco
  raíz. Si ``process`` cerrara y reabriera todo en cada entrada, ese marco
  aparecería dos veces abierto — el caso lo vería. Con una sola entrada, o con
  pilas disjuntas, las dos implementaciones darían el mismo resultado.
* la **deduplicación de marcos** se mide con el mismo marco en dos entradas
  distintas: comparten identificador y la tabla tiene una sola fila. Sin la
  memoria de ``frames_indexes`` habría dos.
* el **signo del diferencial de memoria** se mide con una serie que baja y
  vuelve a subir. Si se contara el valor absoluto, la bajada aportaría peso y
  el total no cuadraría; con una serie monótona los dos códigos coinciden.
* el **acortado del marco SQL** se mide con una consulta que **supera** los
  150 caracteres del acortador. Con una consulta corta, ``shorten`` devuelve
  el texto entero y el caso pasaría aunque el acortador no existiera.
"""
import pytest

from tools.speedscope import Speedscope, shorten

#: Los parámetros que ``add_default`` exige; la fuente los recibe del
#: perfilador, que los arma desde la query string de la petición.
DEFAULT_PARAMS = {
    'combined_profile': False,
    'sql_no_gap_profile': False,
    'sql_density_profile': False,
    'frames_profile': True,
}


def raw_frame(filename, lineno, method, text):
    """Un marco crudo, con la forma de cuatro campos que el colector emite."""
    return (filename, lineno, method, text)


def crude(*methods):
    """Pila **cruda** de N marcos, uno por método, con sus cuatro campos.

    Lo que pasa por :meth:`Speedscope.add` llega sin convertir — es
    ``convert_stack`` quien lo reescribe a la forma de tres campos. Lo que se
    entrega directo a ``process`` o ``stack_to_ids`` va ya convertido, y por eso
    esos casos escriben la tupla de tres a mano.
    """
    return [raw_frame(f'/{m}.py', i * 10, m, f'  {m}()')
            for i, m in enumerate(methods, start=1)]


def entry(stack, start, time=None, **extra):
    """Una entrada cruda de perfil, con su pila y su instante de inicio."""
    data = {'stack': stack, 'start': start}
    if time is not None:
        data['time'] = time
    data.update(extra)
    return data


class TestConvertStack:
    """La posición del marco viene de su llamador, no de sí mismo."""

    def test_the_frame_cites_the_position_of_its_caller(self):
        scope = Speedscope()
        stack = [
            raw_frame('/app/a.py', 10, 'outer', '    inner()'),
            raw_frame('/app/b.py', 20, 'inner', '    leaf()'),
        ]
        scope.convert_stack(stack)

        # El primero no tiene llamador dentro de la pila: queda sin posición.
        assert stack[0] == ('outer', '', '')
        # El segundo cita dónde estaba el primero cuando llamó.
        assert stack[1] == ('inner', 'called at /app/a.py (inner())', 10)

    def test_the_stack_is_rewritten_in_place(self):
        scope = Speedscope()
        stack = [raw_frame('/app/a.py', 1, 'only', '  x')]
        returned = scope.convert_stack(stack)

        assert returned is None
        assert stack[0] == ('only', '', '')


class TestFrameTable:
    """``shared.frames`` deduplica; cada perfil referencia por índice."""

    def test_the_same_frame_keeps_its_identifier(self):
        scope = Speedscope()
        frame = ('method', 'file', 3)

        assert scope.get_frame_id(frame) == 0
        assert scope.get_frame_id(frame) == 0
        assert scope.get_frame_id(('other', '', '')) == 1
        assert scope.frame_count == 2

    def test_a_frame_shared_by_two_entries_has_one_row(self):
        # El control de deduplicación: el marco ``root`` aparece en las dos
        # pilas. Sin la memoria de frames_indexes la tabla tendría dos filas
        # iguales y los identificadores no coincidirían.
        scope = Speedscope()
        shared = ('root', '', '')
        first = scope.stack_to_ids([shared, ('a', '', '')], None)
        second = scope.stack_to_ids([shared, ('b', '', '')], None)

        assert first[0] == second[0]
        assert len(scope.frames_indexes) == 3


class TestStackToIds:
    """El contexto se inserta en su nivel, no al final."""

    def test_the_context_lands_at_its_level(self):
        scope = Speedscope()
        stack = [('a', '', ''), ('b', '', ''), ('c', '', '')]
        ids = scope.stack_to_ids(stack, [(2, {'model': 'res.partner'})])

        names = [frame[0] for frame in scope.frames_indexes]
        # El contexto de nivel 2 va DELANTE del marco de ese nivel, que es el
        # segundo de la pila.
        assert [names[i] for i in ids] == ['a', 'model=res.partner', 'b', 'c']

    def test_a_context_below_the_offset_is_consumed_without_landing(self):
        scope = Speedscope()
        stack = [('a', '', '')]
        ids = scope.stack_to_ids(stack, [(1, {'ignored': 1}), (6, {'kept': 2})],
                                 stack_offset=5)

        names = [frame[0] for frame in scope.frames_indexes]
        assert [names[i] for i in ids] == ['kept=2', 'a']

    def test_aggregate_sql_drops_the_position_of_the_caller(self):
        # Lo que ``aggregate_sql`` borra es el campo del medio —la posición del
        # llamador—, no el número de línea, que sobrevive. Los dos marcos de
        # abajo difieren SÓLO en ese campo.
        scope = Speedscope()
        first = scope.stack_to_ids([('sql(x)', 'called at /a.py (run())', 10)],
                                   None, aggregate_sql=True)
        second = scope.stack_to_ids([('sql(x)', 'called at /b.py (run())', 10)],
                                    None, aggregate_sql=True)

        assert first == second

    def test_without_aggregate_sql_the_caller_separates_them(self):
        scope = Speedscope()
        first = scope.stack_to_ids([('sql(x)', 'called at /a.py (run())', 10)], None)
        second = scope.stack_to_ids([('sql(x)', 'called at /b.py (run())', 10)], None)

        assert first != second


class TestProcess:
    """El emparejamiento de eventos ``O``/``C``."""

    def test_no_entries_gives_no_events(self):
        assert Speedscope().process([]) == []

    def test_the_common_prefix_stays_open_between_entries(self):
        # EL control que puede fallar. Las dos entradas comparten el marco
        # ``root``: con el prefijo común se abre una vez y se cierra una vez.
        # Si process cerrara y reabriera la pila entera en cada entrada,
        # ``root`` aparecería dos veces con type 'O' y el caso lo vería.
        scope = Speedscope()
        root = ('root', '', '')
        events = scope.process([
            entry([root, ('a', '', '')], start=0, time=1),
            entry([root, ('b', '', '')], start=1, time=1),
        ])

        names = [frame[0] for frame in scope.frames_indexes]
        opened = [names[e['frame']] for e in events if e['type'] == 'O']
        assert opened.count('root') == 1
        assert opened.count('a') == 1
        assert opened.count('b') == 1

    def test_without_continuity_every_entry_reopens_its_stack(self):
        # El contraste del caso anterior: con continuous=False el prefijo no
        # se reutiliza, así que ``root`` se abre una vez por entrada. Los dos
        # casos juntos prueban que el parámetro tiene efecto.
        scope = Speedscope()
        root = ('root', '', '')
        events = scope.process([
            entry([root, ('a', '', '')], start=0, time=1),
            entry([root, ('b', '', '')], start=1, time=1),
        ], continuous=False)

        names = [frame[0] for frame in scope.frames_indexes]
        opened = [names[e['frame']] for e in events if e['type'] == 'O']
        assert opened.count('root') == 2

    def test_the_times_are_relative_to_the_first_entry(self):
        scope = Speedscope()
        events = scope.process([entry([('a', '', '')], start=100, time=2)])

        assert events[0]['type'] == 'O'
        assert events[0]['at'] == 0

    def test_a_closing_entry_is_appended_when_the_last_stack_is_open(self):
        scope = Speedscope()
        events = scope.process([entry([('a', '', '')], start=0, time=5)])

        # Sin la entrada de cierre sintética el marco quedaría abierto.
        assert [e['type'] for e in events] == ['O', 'C']
        assert events[-1]['at'] == 5

    def test_hide_gaps_makes_the_entries_contiguous(self):
        scope = Speedscope()
        stack_a = [('a', '', '')]
        stack_b = [('b', '', '')]
        with_gap = scope.process([
            entry(stack_a, start=0, time=1),
            entry(stack_b, start=10, time=1),
        ])
        assert [e['at'] for e in with_gap if e['type'] == 'O'] == [0, 10]

        scope = Speedscope()
        without_gap = scope.process([
            entry([('a', '', '')], start=0, time=1),
            entry([('b', '', '')], start=10, time=1),
        ], hide_gaps=True)
        assert [e['at'] for e in without_gap if e['type'] == 'O'] == [0, 1]

    def test_an_entry_that_starts_before_the_previous_end_is_skipped(self):
        # La guarda ``previous_end > entry_start``: la segunda entrada arranca
        # dentro de la primera, así que no produce eventos propios.
        scope = Speedscope()
        events = scope.process([
            entry([('a', '', '')], start=0, time=10),
            entry([('b', '', '')], start=2, time=1),
        ])

        names = [frame[0] for frame in scope.frames_indexes]
        assert 'b' not in [names[e['frame']] for e in events]

    def test_constant_time_uses_the_index_instead_of_the_clock(self):
        scope = Speedscope()
        events = scope.process([
            entry([('a', '', '')], start=1000, time=7),
            entry([('b', '', '')], start=9999, time=3),
        ], constant_time=True)

        # Los instantes son 0, 1, 2… — el índice de la entrada, no su reloj.
        assert {e['at'] for e in events} <= {0, 1, 2}


class TestAdd:
    """El registro del perfil crudo y su marco sintético de SQL."""

    def test_a_sql_entry_gains_a_frame_with_the_shortened_query(self):
        # El control del acortador: la consulta SUPERA los 150 caracteres que
        # ``shortener.maxstring`` fija. Con una consulta corta, shorten
        # devolvería el texto entero y el caso pasaría sin acortador.
        long_query = 'SELECT ' + ', '.join(f'col_{i}' for i in range(60))
        assert len(long_query) > 150

        scope = Speedscope()
        profile = [entry([raw_frame('/a.py', 1, 'run', 'x')], start=0,
                         query=long_query, full_query=long_query)]
        scope.add('sql', profile)

        sql_frame = profile[0]['stack'][-1]
        assert sql_frame[0] == f'sql({shorten(long_query)})'
        assert len(sql_frame[0]) < len(long_query)
        # El texto completo viaja aparte, para el detalle del visor.
        assert sql_frame[1] == long_query

    def test_a_non_sql_entry_keeps_its_stack_length(self):
        scope = Speedscope()
        profile = [entry([raw_frame('/a.py', 1, 'run', 'x')], start=0)]
        scope.add('frames', profile)

        assert len(profile[0]['stack']) == 1
        assert scope.profiles_raw['frames'] is profile


class TestAddOutput:
    """La salida ``evented`` y su envoltura de pila inicial."""

    def test_an_empty_profile_adds_no_output(self):
        scope = Speedscope()
        scope.add('empty', [])
        scope.add_output(['empty'])

        assert scope.profiles == []

    def test_the_output_declares_seconds_and_its_span(self):
        scope = Speedscope()
        scope.add('frames', [entry(crude('a'), start=0, time=4)])
        scope.add_output(['frames'], complete=False)

        assert len(scope.profiles) == 1
        profile = scope.profiles[0]
        assert profile['type'] == 'evented'
        assert profile['unit'] == 'seconds'
        assert profile['name'] == 'frames'
        assert profile['endValue'] == 4

    def test_constant_time_declares_entries_as_unit(self):
        scope = Speedscope()
        scope.add('frames', [entry(crude('a'), start=0, time=4)])
        scope.add_output(['frames'], complete=False, constant_time=True)

        assert scope.profiles[0]['unit'] == 'entries'

    def test_complete_wraps_the_result_with_the_initial_stack(self):
        init = [raw_frame('/main.py', 1, 'main', 'run()')]
        scope = Speedscope(init_stack_trace=init)
        scope.add('frames', [entry(crude('a'), start=0, time=1)])

        scope.add_output(['frames'], complete=True)
        with_wrapper = len(scope.profiles[0]['events'])

        scope = Speedscope(init_stack_trace=[raw_frame('/main.py', 1, 'main', 'run()')])
        scope.add('frames', [entry(crude('a'), start=0, time=1)])
        scope.add_output(['frames'], complete=False)
        without_wrapper = len(scope.profiles[0]['events'])

        # Un marco inicial añade su apertura y su cierre.
        assert with_wrapper == without_wrapper + 2

    def test_several_names_combine_into_one_output(self):
        scope = Speedscope()
        scope.add('one', [entry(crude('one_a'), start=0, time=1)])
        scope.add('two', [entry(crude('two_b'), start=5, time=1)])
        scope.add_output(['one', 'two'], complete=False, display_name='Combined')

        assert scope.profiles[0]['name'] == 'Combined'
        names = [frame[0] for frame in scope.frames_indexes]
        opened = {names[e['frame']] for e in scope.profiles[0]['events'] if e['type'] == 'O'}
        assert {'one_a', 'two_b'} <= opened


class TestAddMemoryOutput:
    """La salida ``sampled``, con el peso en bytes."""

    def test_only_the_positive_differences_add_weight(self):
        # EL control del signo: la serie baja entre la segunda y la tercera
        # muestra. Si se contara el valor absoluto, el total sería 300 en vez
        # de 200 y habría tres muestras en vez de dos.
        scope = Speedscope()
        scope.add('mem', [
            entry(crude('a'), start=0, memory=1000),
            entry(crude('b'), start=1, memory=1150),
            entry(crude('c'), start=2, memory=1100),
            entry(crude('d'), start=3, memory=1150),
        ])
        scope.add_memory_output(['mem'])

        profile = scope.profiles[0]
        assert profile['type'] == 'sampled'
        assert profile['unit'] == 'bytes'
        assert profile['weights'] == [150, 50]
        assert profile['endValue'] == 200
        assert len(profile['samples']) == 2

    def test_an_entry_without_memory_is_skipped(self):
        scope = Speedscope()
        scope.add('mem', [
            entry(crude('a'), start=0, memory=1000),
            entry(crude('b'), start=1),
            entry(crude('c'), start=2, memory=2000),
        ])
        scope.add_memory_output(['mem'])

        assert scope.profiles == []

    def test_a_monotonically_decreasing_series_adds_no_output(self):
        scope = Speedscope()
        scope.add('mem', [
            entry(crude('a'), start=0, memory=2000),
            entry(crude('b'), start=1, memory=1000),
        ])
        scope.add_memory_output(['mem'])

        assert scope.profiles == []

    def test_the_default_display_name_names_the_keys(self):
        scope = Speedscope()
        scope.add('mem', [
            entry(crude('a'), start=0, memory=1),
            entry(crude('b'), start=1, memory=2),
        ])
        scope.add_memory_output(['mem'])

        assert scope.profiles[0]['name'] == 'Memory mem'


class TestAddDefault:
    """Qué salidas se emiten cuando nadie pidió ninguna."""

    def test_a_frames_profile_gets_one_output(self):
        scope = Speedscope()
        scope.add('frames', [entry(crude('a'), start=0, time=1)])
        scope.add_default(**DEFAULT_PARAMS)

        assert [p['name'] for p in scope.profiles] == ['frames']

    def test_a_frames_profile_is_skipped_when_its_switch_is_off(self):
        scope = Speedscope()
        scope.add('frames', [entry(crude('a'), start=0, time=1)])
        scope.add_default(**{**DEFAULT_PARAMS, 'frames_profile': False})

        assert scope.profiles == []

    def test_a_sql_profile_gets_its_two_views(self):
        scope = Speedscope()
        scope.add('sql', [entry([raw_frame('/a.py', 1, 'run', 'x')], start=0,
                                time=1, query='SELECT 1', full_query='SELECT 1')])
        scope.add_default(**{**DEFAULT_PARAMS,
                             'sql_no_gap_profile': True,
                             'sql_density_profile': True})

        assert [p['name'] for p in scope.profiles] == ['sql (no gap)', 'sql (density)']

    def test_the_combined_output_needs_more_than_one_profile(self):
        scope = Speedscope()
        scope.add('one', [entry(crude('a'), start=0, time=1)])
        scope.add_default(**{**DEFAULT_PARAMS, 'combined_profile': True})

        assert 'Combined' not in [p['name'] for p in scope.profiles]

        scope = Speedscope()
        scope.add('one', [entry(crude('a'), start=0, time=1)])
        scope.add('two', [entry(crude('b'), start=5, time=1)])
        scope.add_default(**{**DEFAULT_PARAMS, 'combined_profile': True})

        assert 'Combined' in [p['name'] for p in scope.profiles]


class TestMake:
    """El documento final que se serializa a JSON."""

    def test_the_document_declares_the_schema_and_the_shared_table(self):
        scope = Speedscope(name='request')
        scope.add('frames', [entry(crude('outer', 'inner'), start=0, time=1)])
        document = scope.make(**DEFAULT_PARAMS)

        assert document['name'] == 'request'
        assert document['activeProfileIndex'] == 0
        assert document['$schema'] == 'https://www.speedscope.app/file-format-schema.json'
        # El marco de cabeza no tiene llamador dentro de la pila; el segundo
        # cita dónde estaba el primero, que es lo que ``convert_stack`` produce.
        assert {'name': 'outer', 'file': '', 'line': ''} in document['shared']['frames']
        assert {'name': 'inner', 'file': 'called at /outer.py (outer())',
                'line': 10} in document['shared']['frames']
        assert document['profiles'] == scope.profiles

    def test_make_does_not_re_add_the_defaults(self):
        scope = Speedscope()
        scope.add('frames', [entry(crude('a'), start=0, time=1)])
        scope.add_output(['frames'], complete=False)
        scope.make(**DEFAULT_PARAMS)

        assert len(scope.profiles) == 1

    @pytest.mark.parametrize('key, expected', [
        ('name', 'Speedscope'),
        ('activeProfileIndex', 0),
    ])
    def test_the_default_header(self, key, expected):
        document = Speedscope().make(**DEFAULT_PARAMS)
        assert document[key] == expected
