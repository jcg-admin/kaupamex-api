"""``tools.cache`` medido contra la fuente ejecutada.

Se carga ``odoo19c: odoo/tools/cache.py`` por ruta —su ``LRU`` sólo se importa
para anotaciones— y se decora **la misma función** con el ``ormcache`` de cada
módulo, de modo que las claves, que contienen el método, son comparables.

Cada lado recibe su contenedor por su vía: la fuente lo busca en
``model.pool._Registry__caches`` y las claves de transacción en
``model.env.cr.cache``; el puerto, en el registro que devuelve
``registry.registry_of`` y en ``_tx_lookups``, que aquí se sustituyen por
contenedores frescos. Los contadores se leen de ``_COUNTERS`` con la misma
clave en los dos lados: ``(base, método)``.

``get_cache_size`` importa ``odoo.models`` y ``odoo.api`` en cada llamada; la
fuente recibe sustitutos durante la llamada.

``ormcache_context`` **no** se compara: en la fuente su ``__init__`` no guarda
``keys`` y cualquier uso falla con ``AttributeError``. El puerto lo guarda; esa
divergencia queda declarada en su docstring y medida aquí en las dos
direcciones. ``log_ormcache_stats`` tampoco: su firma diverge por declaración.

*Métrica:* valores devueltos, llamadas al método envuelto, contenido de la
caché y los siete campos del contador tras cada secuencia; claves por firma;
tamaño estimado de estructuras anidadas.
*Ciega a:* el contenedor real de proceso y la transacción real de Django —los
dos lados reciben sustitutos—, y a toda divergencia que la fuente comparta
con nosotros.
"""
import contextlib
import importlib.util
import pathlib
import sys
import types
import warnings

import pytest

from tools import cache as ported
from tools.lru import LRU

pytestmark = pytest.mark.unit

_REPO = pathlib.Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location(
    'reference_roots_for_cache', _REPO / 'scripts' / 'reference_roots.py')
reference_roots = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(reference_roots)

COUNTER_FIELDS = ('hit', 'miss', 'err', 'tx_hit', 'tx_miss', 'tx_err',
                  'cache_name')


def reference_module():
    try:
        root = pathlib.Path(reference_roots.tree('odoo19c'))
    except Exception:
        return None
    path = root / 'odoo' / 'tools' / 'cache.py'
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location('reference_cache', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def reference():
    module = reference_module()
    if module is None:
        pytest.skip('la referencia no está montada en esta sesión')
    return module


CALLS = []


def compute(self, x, y=1, *, z=0):
    CALLS.append((self._name, x, y, z))
    return (x, y, z)


def keyed(self, x: int, y: 'str' = 'a') -> tuple:
    return (x, y)


class Model:
    """Lo que la fuente lee de un modelo: nombre, registro y transacción."""

    def __init__(self, name, caches, transaction):
        self._name = name
        self.pool = types.SimpleNamespace(
            _Registry__caches=caches, db_name='probe')
        self.env = types.SimpleNamespace(
            cr=types.SimpleNamespace(cache=transaction))


@contextlib.contextmanager
def side(module, monkeypatch):
    """Contenedores frescos; al puerto se le entregan por su propia vía."""
    caches = {'default': LRU(8), 'other': LRU(8)}
    transaction = {}
    if module is ported:
        lookups = set()
        pool = types.SimpleNamespace(_caches=caches, db_name='probe')
        monkeypatch.setattr(ported.registry, 'registry_of',
                            lambda receiver=None: pool)
        monkeypatch.setattr(ported, '_tx_lookups', lambda: lookups)

        def new_transaction():
            lookups.clear()
    else:
        def new_transaction():
            transaction.clear()
    yield Model('res.partner', caches, transaction), caches, new_transaction
    monkeypatch.undo()


def counter_of(module, deco):
    method = deco.__cache__.method
    key = ('probe', method)
    counter = module._COUNTERS[key]
    return tuple(getattr(counter, name) for name in COUNTER_FIELDS)


def outcome(call):
    try:
        return ('value', call())
    except Exception as error:
        return ('raises', type(error).__name__)


def run_sequence(module, monkeypatch):
    CALLS.clear()
    # ``_COUNTERS`` vive en el módulo y sobrevive entre pruebas del proceso:
    # sin vaciarlo, una segunda ejecución partiría de contadores ajenos.
    for key in [k for k in module._COUNTERS
                if compute in (k if isinstance(k, tuple) else (k,))]:
        del module._COUNTERS[key]
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        plain = module.ormcache('x')(compute)
        other = module.ormcache('x', 'z', cache='other')(compute)
        legacy = module.ormcache(skiparg=2)(compute)
    with side(module, monkeypatch) as (model, caches, new_transaction):
        # Un argumento no hashable falla al hashear la clave de transacción,
        # antes del ``try`` de la búsqueda: es conducta, y se compara.
        results = [outcome(call) for call in (
            lambda: plain(model, 1), lambda: plain(model, 1, y=5),
            lambda: plain(model, 2), lambda: other(model, 1, z=3),
            lambda: other(model, 1, z=3), lambda: legacy(model, 4, 9),
            lambda: legacy(model, 4, 9), lambda: plain(model, [1]),
        )]
        plain.__cache__.add_value(model, 7, cache_value='seeded')
        new_transaction()
        results += [outcome(call) for call in (
            lambda: plain(model, 7), lambda: plain(model, 1),
            lambda: other(model, 1, z=3),
        )]
        snapshot = {name: sorted(map(repr, cache.snapshot))
                    for name, cache in caches.items()}
    return (results, list(CALLS), snapshot,
            [counter_of(module, deco) for deco in (plain, other, legacy)])


class TestOrmcacheBehavesLikeTheReference:

    def test_a_call_sequence_matches_the_reference(
            self, reference, monkeypatch):
        theirs = run_sequence(reference, monkeypatch)
        ours = run_sequence(ported, monkeypatch)
        labels = ('results', 'calls', 'caches', 'counters')
        for label, expected, actual in zip(labels, theirs, ours):
            assert actual == expected, label

    @pytest.mark.parametrize('function, args', [
        (compute, (1,)), (compute, (1, 2)), (keyed, (3,)),
        (keyed, (3, 'b')),
    ])
    def test_the_key_is_the_reference_key(self, reference, function, args):
        model = types.SimpleNamespace(_name='res.users')
        keys = []
        for module in (reference, ported):
            for expressions in ((), ('x',), ('x', 'y')):
                deco = module.ormcache(*expressions)(function)
                keys.append(deco.__cache__.key(model, *args))
        half = len(keys) // 2
        assert keys[half:] == keys[:half]

    def test_a_bound_ormcache_refuses_a_second_method(self, reference):
        for module in (reference, ported):
            deco = module.ormcache('x')
            deco(compute)
            with pytest.raises(AssertionError):
                deco(keyed)

    def test_the_counter_ratios_match(self, reference):
        values = []
        for module in (reference, ported):
            counter = module.ormcache_counter()
            row = [counter.ratio, counter.tx_ratio, counter.tx_calls]
            counter.hit, counter.miss = 3, 1
            counter.tx_hit, counter.tx_miss = 1, 3
            row += [counter.ratio, counter.tx_ratio, counter.tx_calls]
            values.append(row)
        assert values[0] == values[1]
        assert ported.ormcache_counter.__slots__ == \
            reference.ormcache_counter.__slots__


class TestOrmcacheContextDivergence:
    """La divergencia declarada, medida en las dos direcciones."""

    def test_the_reference_cannot_build_a_context_key(self, reference):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with pytest.raises(AttributeError):
                reference.ormcache_context('x', keys=('lang',))(compute)

    def test_the_port_keeps_the_keys(self):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            deco = ported.ormcache_context('x', keys=('lang',))

            def method(self, x, context=None):
                return x

            bound = deco(method)
        key = bound.__cache__.key(types.SimpleNamespace(_name='m'), 1,
                                  context={'lang': 'es_MX'})
        assert key[-1] == ('es_MX',)


@contextlib.contextmanager
def size_stand_ins():
    """``odoo.models`` y ``odoo.api`` sustitutos, sólo durante la llamada."""
    names = ('odoo', 'odoo.models', 'odoo.api')
    saved = {name: sys.modules.get(name) for name in names}
    modules = {name: types.ModuleType(name) for name in names}
    modules['odoo.models'].BaseModel = type('BaseModel', (), {})
    modules['odoo.api'].Environment = type('Environment', (), {})
    sys.modules.update(modules)
    try:
        yield
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


class Slotted:
    __slots__ = ('a', '__b')

    def __init__(self):
        self.a = [1, 2, 'x' * 50]
        self.__b = {'k': (3, 4)}


class Plain:
    """Con ``__dict__``: la fuente encola ``object.__dict__``, no el suyo."""

    def __init__(self):
        self.payload = ['y' * 500, {'deep': list(range(50))}]


SHAPES = (
    None, 42, 'text', b'bytes', [1, [2, [3]]], {'a': {'b': [1, 2]}},
    ({1, 2}, frozenset({3})), Slotted(), [Slotted(), Slotted()], Plain(),
    [Plain(), Slotted()],
)
#: Ids fijos: el ``repr`` de una instancia lleva su dirección de memoria, que
#: cambia entre procesos, y con ``-n`` cada trabajador recolectaría otras
#: pruebas.
SHAPE_IDS = ('none', 'int', 'str', 'bytes', 'nested-list', 'nested-dict',
             'sets', 'slotted', 'slotted-list', 'plain', 'plain-and-slotted')


class TestGetCacheSizeMatchesTheReference:

    @pytest.mark.parametrize('shape', SHAPES, ids=SHAPE_IDS)
    def test_the_estimate_matches(self, reference, shape):
        with size_stand_ins():
            expected = reference.get_cache_size(shape)
        assert ported.get_cache_size(shape) == expected

    def test_shared_ids_are_counted_once(self, reference):
        shared = ['x' * 100]
        payload = [shared, shared]
        with size_stand_ins():
            expected = reference.get_cache_size(payload)
        assert ported.get_cache_size(payload) == expected


class TestCacheLiterally:
    """Un caso escrito a mano: el diferencial no dice cuál se rompió."""

    def test_a_second_call_is_served_from_the_cache(self, monkeypatch):
        CALLS.clear()
        deco = ported.ormcache('x')(compute)
        with side(ported, monkeypatch) as (model, caches, _new):
            assert deco(model, 5) == deco(model, 5) == (5, 1, 0)
        assert len(CALLS) == 1
