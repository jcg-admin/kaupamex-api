"""``tools.intervals`` — la coleccion de intervalos disjuntos y ordenados.

Adapta ``odoo19c: odoo/addons/base/tests/test_intervals.py`` (242 lineas). La
fuente lo escribe como ``TransactionCase`` y usa ``self.env['base']`` como
conjunto empty de registros; aqui no hace falta base de datos: el modulo solo
pide de ese tercer elemento que sepa ``union()``, asi que un ``frozenset``
cumple el contrato y el caso corre sin transaccion.

Los casos se escribieron ANTES del modulo, y el control discrimina: contra un
``src/tools/intervals.py`` inexistente el archivo entero falla en la
importacion.
"""
from datetime import datetime

import pytest

from tools.intervals import Intervals, intervals_overlap, invert_intervals


def ints(pairs):
    """Levanta pares a triples con un conjunto empty de registros."""
    empty = frozenset()
    return [(a, b, empty) for a, b in pairs]


class TestUnion:
    """``Intervals(...)`` normaliza: ordena, fusiona y descarta lo empty."""

    @pytest.mark.parametrize('given, expected', [
        ([(1, 2), (3, 4)], [(1, 2), (3, 4)]),
        ([(1, 2), (2, 4)], [(1, 4)]),
        ([(1, 3), (2, 4)], [(1, 4)]),
        ([(1, 4), (2, 3)], [(1, 4)]),
        ([(3, 4), (1, 2)], [(1, 2), (3, 4)]),
        ([(2, 4), (1, 2)], [(1, 4)]),
        ([(2, 4), (1, 3)], [(1, 4)]),
        ([(2, 3), (1, 4)], [(1, 4)]),
    ])
    def test_it_merges_what_touches(self, given, expected):
        assert list(Intervals(ints(given))) == ints(expected)

    def test_the_empty_interval_disappears(self):
        """``start < stop`` es la guarda de ``_boundaries``: (7, 7) no entra."""
        assert list(Intervals(ints([(7, 7)]))) == []

    def test_it_is_falsy_when_it_holds_nothing(self):
        assert not Intervals()
        assert len(Intervals()) == 0
        assert Intervals(ints([(1, 2)]))

    def test_the_operator_is_the_union(self):
        a, b = Intervals(ints([(1, 2)])), Intervals(ints([(2, 4)]))
        assert list(a | b) == ints([(1, 4)])

    def test_it_walks_backwards(self):
        collection = Intervals(ints([(1, 2), (3, 4)]))
        assert list(reversed(collection)) == ints([(3, 4), (1, 2)])


class TestIntersection:
    @pytest.mark.parametrize('a, b, expected', [
        ([(10, 20)], [(5, 8)], []),
        ([(10, 20)], [(5, 10)], []),
        ([(10, 20)], [(5, 15)], [(10, 15)]),
        ([(10, 20)], [(5, 20)], [(10, 20)]),
        ([(10, 20)], [(5, 25)], [(10, 20)]),
        ([(10, 20)], [(10, 15)], [(10, 15)]),
        ([(10, 20)], [(10, 20)], [(10, 20)]),
        ([(10, 20)], [(10, 25)], [(10, 20)]),
        ([(10, 20)], [(15, 18)], [(15, 18)]),
        ([(10, 20)], [(15, 20)], [(15, 20)]),
        ([(10, 20)], [(15, 25)], [(15, 20)]),
        ([(10, 20)], [(20, 25)], []),
        ([(0, 5), (10, 15), (20, 25), (30, 35)],
         [(6, 7), (9, 12), (13, 17), (22, 23), (24, 40)],
         [(10, 12), (13, 15), (22, 23), (24, 25), (30, 35)]),
    ])
    def test_it_keeps_only_what_both_cover(self, a, b, expected):
        assert list(Intervals(ints(a)) & Intervals(ints(b))) == ints(expected)


class TestDifference:
    @pytest.mark.parametrize('a, b, expected', [
        ([(10, 20)], [(5, 8)], [(10, 20)]),
        ([(10, 20)], [(5, 10)], [(10, 20)]),
        ([(10, 20)], [(5, 15)], [(15, 20)]),
        ([(10, 20)], [(5, 20)], []),
        ([(10, 20)], [(5, 25)], []),
        ([(10, 20)], [(10, 15)], [(15, 20)]),
        ([(10, 20)], [(10, 20)], []),
        ([(10, 20)], [(10, 25)], []),
        ([(10, 20)], [(15, 18)], [(10, 15), (18, 20)]),
        ([(10, 20)], [(15, 20)], [(10, 15)]),
        ([(10, 20)], [(15, 25)], [(10, 15)]),
        ([(10, 20)], [(20, 25)], [(10, 20)]),
        ([(0, 5), (10, 15), (20, 25), (30, 35)],
         [(6, 7), (9, 12), (13, 17), (22, 23), (24, 40)],
         [(0, 5), (12, 13), (20, 22), (23, 24)]),
    ])
    def test_it_removes_what_the_other_covers(self, a, b, expected):
        assert list(Intervals(ints(a)) - Intervals(ints(b))) == ints(expected)


class TestKeepDistinct:
    """``keep_distinct=True`` NO fusiona lo adyacente — solo lo que solapa."""

    @pytest.mark.parametrize('given, expected', [
        ([(1, 2), (3, 4)], [(1, 2), (3, 4)]),
        ([(1, 2), (2, 4)], [(1, 2), (2, 4)]),
        ([(1, 3), (2, 4)], [(1, 4)]),
        ([(1, 4), (2, 3)], [(1, 4)]),
        ([(1, 4), (1, 4)], [(1, 4)]),
        ([(3, 4), (1, 2)], [(1, 2), (3, 4)]),
        ([(2, 4), (1, 2)], [(1, 2), (2, 4)]),
        ([(2, 4), (1, 3)], [(1, 4)]),
        ([(2, 3), (1, 4)], [(1, 4)]),
    ])
    def test_the_adjacent_stays_apart(self, given, expected):
        assert list(Intervals(ints(given), keep_distinct=True)) == ints(expected)

    def test_the_flag_is_the_discriminator(self):
        """El control: la MISMA given da dos resultados segun la bandera.

        Sin este caso, los dos bloques de arriba podrian estar midiendo el
        mismo camino de codigo y nadie lo notaria.
        """
        given = ints([(1, 2), (2, 4)])
        assert list(Intervals(given, keep_distinct=True)) == ints([(1, 2), (2, 4)])
        assert list(Intervals(given, keep_distinct=False)) == ints([(1, 4)])

    @pytest.mark.parametrize('a, b, expected', [
        ([(10, 20)], [(5, 15)], [(10, 15)]),
        ([(10, 20)], [(15, 18)], [(15, 18)]),
        ([(0, 5), (10, 15), (20, 25), (30, 35)],
         [(6, 7), (9, 12), (13, 17), (22, 23), (24, 40)],
         [(10, 12), (13, 15), (22, 23), (24, 25), (30, 35)]),
    ])
    def test_it_intersects_keeping_the_flag(self, a, b, expected):
        collection = Intervals(ints(a), keep_distinct=True) & Intervals(
            ints(b), keep_distinct=True)
        assert list(collection) == ints(expected)

    @pytest.mark.parametrize('a, b, expected', [
        ([(10, 20)], [(5, 15)], [(15, 20)]),
        ([(10, 20)], [(15, 18)], [(10, 15), (18, 20)]),
        ([(0, 5), (10, 15), (20, 25), (30, 35)],
         [(6, 7), (9, 12), (13, 17), (22, 23), (24, 40)],
         [(0, 5), (12, 13), (20, 22), (23, 24)]),
    ])
    def test_it_subtracts_keeping_the_flag(self, a, b, expected):
        collection = Intervals(ints(a), keep_distinct=True) - Intervals(
            ints(b), keep_distinct=True)
        assert list(collection) == ints(expected)

    def test_the_left_operand_dictates_the_flag(self):
        """Y el resultado conserva sus items tras una segunda operacion.

        Es el caso que la fuente escribe: si ``C`` sale con la bandera del
        izquierdo pero sin preservar ``_items``, la resta contra el empty
        levanta. Aqui se mide que no levanta y que el contenido sobrevive.
        """
        a = Intervals(ints([(0, 10)]), keep_distinct=False)
        b = Intervals(ints([(-5, 5), (5, 15)]), keep_distinct=True)

        c = a & b
        assert c._keep_distinct is False
        assert len(c) == 1
        assert list(c) == ints([(0, 10)])

        c = c - Intervals()
        assert c._keep_distinct is False
        assert c._items == ints([(0, 10)])


class TestOverlap:
    @pytest.mark.parametrize('a, b, overlaps', [
        ((datetime(2023, 2, 14), datetime(2023, 2, 15)),
         (datetime(2023, 2, 15), datetime(2023, 2, 16)), False),
        ((datetime(2023, 2, 14), datetime(2023, 2, 15)),
         (datetime(2023, 2, 13), datetime(2023, 2, 16)), True),
        ((datetime(2023, 2, 13), datetime(2023, 2, 16)),
         (datetime(2023, 2, 14), datetime(2023, 2, 15)), True),
        ((datetime(2023, 2, 13), datetime(2023, 2, 16)),
         (datetime(2023, 2, 15), datetime(2023, 2, 17)), True),
    ])
    def test_it_answers_whether_two_intervals_meet(self, a, b, overlaps):
        assert intervals_overlap(a, b) is overlaps


#: Los diez intervalos de la fuente: no adyacente, de longitud cero,
#: multi-adyacente, solapados, contenido, y desordenado no adyacente.
_INTERVALS = [
    (datetime(2023, 2, 5), datetime(2023, 2, 6)),
    (datetime(2023, 2, 7), datetime(2023, 2, 7)),
    (datetime(2023, 2, 9), datetime(2023, 2, 10)),
    (datetime(2023, 2, 10), datetime(2023, 2, 11)),
    (datetime(2023, 2, 11), datetime(2023, 2, 12)),
    (datetime(2023, 2, 13), datetime(2023, 2, 15)),
    (datetime(2023, 2, 14), datetime(2023, 2, 18)),
    (datetime(2023, 2, 15), datetime(2023, 2, 16)),
    (datetime(2023, 2, 25), datetime(2023, 3, 10)),
    (datetime(2023, 2, 20), datetime(2023, 2, 22)),
]


class TestInversion:
    """``invert_intervals`` convierte lo disponible en lo no disponible."""

    @pytest.mark.parametrize('bounds, expected', [
        ((datetime(2023, 1, 1), datetime(2023, 4, 1)), [
            (datetime(2023, 1, 1), datetime(2023, 2, 5)),
            (datetime(2023, 2, 6), datetime(2023, 2, 9)),
            (datetime(2023, 2, 12), datetime(2023, 2, 13)),
            (datetime(2023, 2, 18), datetime(2023, 2, 20)),
            (datetime(2023, 2, 22), datetime(2023, 2, 25)),
            (datetime(2023, 3, 10), datetime(2023, 4, 1)),
        ]),
        ((datetime(2023, 2, 5), datetime(2023, 3, 10)), [
            (datetime(2023, 2, 6), datetime(2023, 2, 9)),
            (datetime(2023, 2, 12), datetime(2023, 2, 13)),
            (datetime(2023, 2, 18), datetime(2023, 2, 20)),
            (datetime(2023, 2, 22), datetime(2023, 2, 25)),
        ]),
        ((datetime(2023, 2, 9), datetime(2023, 2, 12)), []),
        ((datetime(2023, 2, 6), datetime(2023, 2, 9)),
         [(datetime(2023, 2, 6), datetime(2023, 2, 9))]),
        ((datetime(2023, 2, 8), datetime(2023, 2, 11)),
         [(datetime(2023, 2, 8), datetime(2023, 2, 9))]),
        ((datetime(2023, 2, 20), datetime(2023, 2, 24)),
         [(datetime(2023, 2, 22), datetime(2023, 2, 24))]),
        ((datetime(2023, 2, 14), datetime(2023, 2, 16)), []),
        ((datetime(2023, 2, 22), datetime(2023, 2, 25)),
         [(datetime(2023, 2, 22), datetime(2023, 2, 25))]),
        ((datetime(2023, 2, 1), datetime(2023, 2, 5)),
         [(datetime(2023, 2, 1), datetime(2023, 2, 5))]),
    ])
    def test_it_returns_the_gaps(self, bounds, expected):
        start, stop = bounds
        assert invert_intervals(_INTERVALS, start, stop) == expected


class TestDeprecated:
    """Los dos que la fuente conserva avisando: se portan CON su aviso."""

    def test_remove_warns_and_removes(self):
        collection = Intervals(ints([(1, 2), (3, 4)]))
        with pytest.warns(DeprecationWarning):
            collection.remove(ints([(1, 2)])[0])
        assert list(collection) == ints([(3, 4)])

    def test_items_warns_and_returns_the_list(self):
        collection = Intervals(ints([(1, 2)]))
        with pytest.warns(DeprecationWarning):
            assert collection.items() == ints([(1, 2)])
