"""``Intervals`` contra la referencia ejecutada — ``odoo19c:
odoo/tools/intervals.py:15-117``.

Oráculo diferencial: el ``intervals.py`` de la referencia sólo depende de la
biblioteca estándar, así que se compila desde su texto —sin importarlo, para
no escribir ``__pycache__`` en ``odoo-tools``— y se compara con el nuestro
sobre la misma matriz. Las aserciones literales repiten lo leído del cuerpo y
siguen discriminando si el árbol no está montado.

Mutaciones que lo hacen caer: no fusionar lo adyacente (cae la matriz y la de
fusión); ignorar ``keep_distinct`` (cae la matriz); no avisar en ``remove`` o
``items`` (caen las de desuso).
"""
import pathlib
import types
import warnings

import pytest

import reference_roots
from tools import intervals

REFERENCE_FILE = (reference_roots.tree('odoo19c')
                  / 'odoo' / 'tools' / 'intervals.py')

CASES = (
    [(1, 3, {'a'}), (3, 5, {'b'})],
    [(1, 4, {'a'}), (2, 6, {'b'}), (8, 9, {'c'})],
    [(5, 5, {'a'}), (6, 7, {'b'})],
    [(10, 12, {'x'}), (1, 2, {'y'})],
    [],
)
OTHERS = (
    [(2, 4, {'o'})],
    [(0, 10, {'o'})],
    [(6, 8, {'o'}), (11, 12, {'p'})],
    [],
)


def _reference_module():
    source = pathlib.Path(REFERENCE_FILE).read_text()
    module = types.ModuleType('reference_tools_intervals')
    exec(compile(source, str(REFERENCE_FILE), 'exec'), module.__dict__)
    return module


def _norm(items):
    return [(a, b, sorted(r)) for a, b, r in items]


def _behaviour(module):
    rows = []
    for distinct in (False, True):
        for case in CASES:
            own = module.Intervals(case, keep_distinct=distinct)
            rows.append(('build', distinct, _norm(own), bool(own), len(own),
                         _norm(reversed(own))))
            for other in OTHERS:
                peer = module.Intervals(other, keep_distinct=distinct)
                rows.append(('or', distinct, _norm(own | peer)))
                rows.append(('and', distinct, _norm(own & peer)))
                rows.append(('sub', distinct, _norm(own - peer)))
    rows.append(('bounds', [(v, f, sorted(r)) for v, f, r in
                            module._boundaries(CASES[1], 'start', 'stop')]))
    return rows


@pytest.mark.skipif(
    not REFERENCE_FILE.is_file(),
    reason=f'referencia ausente: {REFERENCE_FILE} no existe (odoo-tools no '
           'montado; ver referencia-odoo-gobierna-las-decisiones.md)')
class TestIntervalsBehaveLikeTheReference:

    def test_every_case_matches_the_reference_module(self):
        expected = _behaviour(_reference_module())
        observed = _behaviour(intervals)
        assert len(expected) == len(observed)
        mismatches = [(e, o) for e, o in zip(expected, observed) if e != o]
        assert not mismatches, mismatches[:3]


class TestIntervalsLiteralContract:

    def test_adjacent_intervals_merge_by_default(self):
        merged = intervals.Intervals([(1, 3, {'a'}), (3, 5, {'b'})])
        assert _norm(merged) == [(1, 5, ['a', 'b'])]
        assert len(merged) == 1

    def test_keep_distinct_leaves_them_apart(self):
        kept = intervals.Intervals([(1, 3, {'a'}), (3, 5, {'b'})],
                                   keep_distinct=True)
        assert len(kept) == 2

    def test_remove_and_items_are_deprecated(self):
        values = intervals.Intervals([(1, 2, {'a'})])
        with pytest.warns(DeprecationWarning):
            assert _norm(values.items()) == [(1, 2, ['a'])]
        with pytest.warns(DeprecationWarning):
            values.remove((1, 2, {'a'}))
        assert not values

    def test_the_boundaries_skip_empty_intervals(self):
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            bounds = list(intervals._boundaries([(2, 2, {'a'}),
                                                 (1, 3, {'b'})], 'o', 'c'))
        assert bounds == [(1, 'o', {'b'}), (3, 'c', {'b'})]
