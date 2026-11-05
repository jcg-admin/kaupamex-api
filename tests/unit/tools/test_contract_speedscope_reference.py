"""``tools.speedscope`` medido contra la fuente ejecutada.

``test_speedscope.py`` fija a mano los contratos que el visor consume. Este
archivo carga ``odoo19c: odoo/tools/speedscope.py`` por ruta —sólo importa
``reprlib``— y le da a los dos módulos los mismos perfiles crudos de los tres
colectores (marcos con contexto de ejecución, SQL con entradas solapadas y
memoria que sube y baja), para comparar el documento entero que sale de
``make``: la tabla de marcos compartida y cada perfil, evento por evento.

Cada lado recibe su propia copia de los perfiles, porque ``add`` y
``process`` los modifican en el sitio.

*Métrica:* igualdad del documento que devuelve ``make`` —o el nombre de la
excepción— para las dieciséis combinaciones de los cuatro indicadores de
``add_default`` y para seis salidas explícitas.
*Ciega a:* perfiles fuera de esta rejilla y a toda divergencia que la fuente
comparta con nosotros.
"""
import copy
import importlib.util
import itertools
import pathlib

import pytest

from tools import speedscope as ported

pytestmark = pytest.mark.unit

_REPO = pathlib.Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location(
    'reference_roots_for_speedscope', _REPO / 'scripts' / 'reference_roots.py')
reference_roots = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(reference_roots)

FLAGS = ('combined_profile', 'sql_no_gap_profile', 'sql_density_profile',
         'frames_profile')
LONG_QUERY = 'SELECT ' + ', '.join(f'column_{n}' for n in range(40))


def reference_module():
    try:
        root = pathlib.Path(reference_roots.tree('odoo19c'))
    except Exception:
        return None
    path = root / 'odoo' / 'tools' / 'speedscope.py'
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location('reference_speedscope', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def reference():
    module = reference_module()
    if module is None:
        pytest.skip('la referencia no está montada en esta sesión')
    return module


def frame(name, line):
    return (f'/app/{name}.py', line, name, f'    {name}()')


INIT_STACK = [frame('server', 1), frame('dispatch', 2)]
PROFILES = {
    'frames': [
        {'stack': [frame('root', 10), frame('a', 11)], 'start': 1.0,
         'exec_context': ((3, {'req': 1}),)},
        {'stack': [frame('root', 10), frame('b', 12)], 'start': 1.5},
        {'stack': [frame('root', 10), frame('b', 12), frame('c', 13)],
         'start': 2.25, 'exec_context': ((3, {'req': 1}), (4, {'step': 2}))},
        {'stack': [frame('other', 20)], 'start': 4.0},
    ],
    'sql': [
        {'stack': [frame('root', 10)], 'start': 1.1, 'time': 0.4,
         'query': 'SELECT 1', 'full_query': 'SELECT 1'},
        {'stack': [frame('root', 10), frame('a', 11)], 'start': 1.3,
         'time': 0.1, 'query': LONG_QUERY, 'full_query': LONG_QUERY},
        {'stack': [frame('root', 10)], 'start': 2.0, 'time': 0.2,
         'query': 'SELECT 2', 'full_query': 'SELECT 2'},
    ],
    'memory': [
        {'stack': [frame('root', 10)], 'start': 1.0, 'memory': 100},
        {'stack': [frame('root', 10), frame('a', 11)], 'start': 1.2,
         'memory': 160},
        {'stack': [frame('root', 10)], 'start': 1.4, 'memory': 120},
        {'stack': [frame('b', 12)], 'start': 1.6, 'memory': 200,
         'exec_context': ((3, {'req': 9}),)},
        # Dos lecturas iguales: una diferencia nula no es una asignación.
        {'stack': [frame('c', 13)], 'start': 1.7, 'memory': 200},
        {'stack': [frame('c', 13)], 'start': 1.75, 'memory': 230},
        {'stack': [frame('b', 12)], 'start': 1.8},
    ],
}


def scope(module, keys=('frames', 'sql', 'memory')):
    """Un ``Speedscope`` nuevo con copias propias de los perfiles pedidos."""
    result = module.Speedscope(name='Probe', init_stack_trace=copy.deepcopy(
        INIT_STACK))
    for key in keys:
        result.add(key, copy.deepcopy(PROFILES[key]))
    return result


def documents(module):
    """``(etiqueta, invocación)`` que producen un documento completo."""
    grid = []
    for values in itertools.product((False, True), repeat=len(FLAGS)):
        params = dict(zip(FLAGS, values))
        grid.append((f'make {params}',
                     lambda p=params: scope(module).make(**p)))
    grid += [
        ('constant time', lambda: scope(module).add_output(
            ['sql'], constant_time=True).make()),
        ('incomplete, no context', lambda: scope(module).add_output(
            ['frames', 'sql'], complete=False, use_context=False).make()),
        ('aggregated sql', lambda: scope(module).add_output(
            ['sql'], aggregate_sql=True, hide_gaps=True).make()),
        ('memory', lambda: scope(module).add_memory_output(
            ['memory']).make()),
        ('memory without context', lambda: scope(module).add_memory_output(
            ['memory', 'frames'], display_name='M', use_context=False).make()),
        ('unknown and empty names', lambda: scope(module, ()).add_output(
            ['missing']).add_memory_output(['missing']).make()),
    ]
    return grid


def outcome(call):
    try:
        return ('value', call())
    except Exception as error:
        return ('raises', type(error).__name__)


class TestSpeedscopeBehavesLikeTheReference:

    def test_every_document_matches_the_reference(self, reference):
        theirs, ours = documents(reference), documents(ported)
        divergences = [
            label
            for (label, their_call), (_label, our_call) in zip(theirs, ours)
            if outcome(their_call) != outcome(our_call)]
        assert len(theirs) >= 22
        assert not divergences, divergences[:3]

    def test_the_grid_produces_events_and_samples(self, reference):
        """Sin perfiles no vacíos, la igualdad de arriba no mediría nada."""
        kinds = set()
        for _label, call in documents(reference):
            result = outcome(call)
            if result[0] == 'value':
                kinds.update(p['type'] for p in result[1]['profiles'])
        assert kinds == {'evented', 'sampled'}

    def test_the_shortener_is_the_reference_shortener(self, reference):
        assert ported.shorten(LONG_QUERY) == reference.shorten(LONG_QUERY)
        assert ported.shortener.maxstring == reference.shortener.maxstring


class TestSpeedscopeLiterally:
    """Un caso escrito a mano: el diferencial no dice cuál se rompió."""

    def test_an_overlapping_entry_is_skipped(self):
        events = ported.Speedscope().process([
            {'stack': [('a', '', '')], 'start': 0.0, 'time': 1.0},
            {'stack': [('b', '', '')], 'start': 0.5, 'time': 0.1},
            {'stack': [], 'start': 2.0},
        ])
        opened = [e for e in events if e['type'] == 'O']
        assert len(opened) == 1
