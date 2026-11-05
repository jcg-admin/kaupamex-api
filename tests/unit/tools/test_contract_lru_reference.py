"""``LRU`` contra la referencia ejecutada — ``odoo19c: odoo/tools/lru.py``.

Oráculo diferencial: el ``lru.py`` de la referencia sólo importa la
biblioteca estándar y ``SENTINEL`` de ``.misc``. Se compila desde su texto
—sin importarlo, para no escribir ``__pycache__`` en ``odoo-tools``— dentro de
un paquete sustituto cuyo ``misc`` expone nuestro ``SENTINEL``, que el código
sólo usa como marca. El sustituto se retira al terminar. Las aserciones
literales repiten lo leído del cuerpo y siguen discriminando si el árbol no
está montado.

Mutaciones que lo hacen caer: no expulsar el menos reciente (cae la matriz y
la de capacidad); no mover al final al leer (cae la matriz y la de orden);
aceptar una capacidad no positiva (cae la de la guarda).
"""
import contextlib
import pathlib
import sys
import types

import pytest

import reference_roots
from tools import lru
from tools.misc import SENTINEL

REFERENCE_FILE = (reference_roots.tree('odoo19c')
                  / 'odoo' / 'tools' / 'lru.py')
PACKAGE = 'reference_tools_package'


@contextlib.contextmanager
def _reference_package():
    package = types.ModuleType(PACKAGE)
    package.__path__ = []
    misc = types.ModuleType(f'{PACKAGE}.misc')
    misc.SENTINEL = SENTINEL
    shims = {PACKAGE: package, f'{PACKAGE}.misc': misc}
    saved = {name: sys.modules.get(name) for name in shims}
    sys.modules.update(shims)
    try:
        yield
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def _reference_module():
    source = pathlib.Path(REFERENCE_FILE).read_text()
    module = types.ModuleType(f'{PACKAGE}.lru')
    module.__package__ = PACKAGE
    with _reference_package():
        exec(compile(source, str(REFERENCE_FILE), 'exec'), module.__dict__)
    return module


def _outcome(call):
    try:
        return ('ok', call())
    except Exception as error:
        return ('raise', type(error).__name__)


def _behaviour(module):
    rows = []
    cache = module.LRU(3, [('a', 1), ('b', 2)])
    rows.append(('init', list(cache), len(cache), cache.count))
    cache['c'] = 3
    rows.append(('read', cache['a'], list(cache)))
    cache['d'] = 4
    rows.append(('evict', list(cache), 'b' in cache, cache.snapshot))
    rows.append(('pop', cache.pop('c'), _outcome(lambda: cache.pop('zz')),
                 cache.pop('zz', 'dflt'), list(cache)))
    del cache['a']
    rows.append(('del', list(cache), _outcome(lambda: cache['a'])))
    cache.update({'x': 9, 'y': 8, 'z': 7})
    rows.append(('update', list(cache)))
    cache.count = 1
    rows.append(('shrink', list(cache), cache.count))
    rows.append(('bad', _outcome(lambda: module.LRU(0))))
    cache.clear()
    rows.append(('clear', list(cache), len(cache)))
    rows.append(('slots', module.LRU.__slots__))
    return rows


@pytest.mark.skipif(
    not REFERENCE_FILE.is_file(),
    reason=f'referencia ausente: {REFERENCE_FILE} no existe (odoo-tools no '
           'montado; ver referencia-odoo-gobierna-las-decisiones.md)')
class TestLruBehavesLikeTheReference:

    def test_every_step_matches_the_reference_module(self):
        expected = _behaviour(_reference_module())
        observed = _behaviour(lru)
        assert len(expected) == len(observed)
        mismatches = [(e, o) for e, o in zip(expected, observed) if e != o]
        assert not mismatches, mismatches[:3]

    def test_the_stand_in_package_is_withdrawn(self):
        _reference_module()
        assert PACKAGE not in sys.modules


class TestLruLiteralContract:

    def test_the_least_recent_is_evicted(self):
        cache = lru.LRU(2, [('a', 1), ('b', 2)])
        cache['c'] = 3
        assert list(cache) == ['b', 'c']

    def test_reading_makes_a_key_recent(self):
        cache = lru.LRU(2, [('a', 1), ('b', 2)])
        assert cache['a'] == 1
        cache['c'] = 3
        assert list(cache) == ['a', 'c']

    def test_the_count_must_be_positive(self):
        with pytest.raises(AssertionError):
            lru.LRU(0)
