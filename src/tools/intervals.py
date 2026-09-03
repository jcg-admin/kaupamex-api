"""Intervalos disjuntos y ordenados — adaptacion de ``odoo19c:
odoo/tools/intervals.py`` (``odoo-tools@622ddc2a``, LGPL-3 segun el
``__manifest__.py`` de su addon raiz: copia + adaptacion con atribucion
preservada, DEC-KX-03).

Que resuelve: la coleccion ``Intervals``, que normaliza una lista de triples
``(inicio, fin, registros)`` en un conjunto **ordenado y disjunto**, y sabe
unir, intersecar y restar; mas los dos ayudantes sueltos que trabajan sobre
pares — ``intervals_overlap`` y ``invert_intervals``.

**Se portan 4 de 4 simbolos** (``_boundaries``, ``Intervals``,
``intervals_overlap``, ``invert_intervals``). El archivo aterriza en
``src/tools/`` porque ``src/tools`` ↔ ``odoo/tools`` es una raiz espejada
(``atributos-de-clase-de-modelo.md``, segunda clausula): el hogar del simbolo
lo fija la referencia, no la conveniencia del primer consumidor.

Por que entra ahora
===================

Tres archivos del arbol declaraban su ausencia como impedimento por
escrito, nombrando este mismo motor de intervalos:
``addons/hr/models/resource.py``, ``addons/hr/models/hr_employee.py`` y
``addons/resource/models/resource_resource.py``. Con el modulo construido,
``ResourceCalendar._work_intervals_batch`` y sus consumidores dejan de
esperarlo.

Medido en la referencia: **20** archivos lo importan, el conteo mas alto de
los veinte modulos de ``odoo/tools`` que faltaban en esta raiz (tarea #338).

El stack lo TRAE — no hay nada que construir
=============================================

El modulo es CPython puro: ``itertools.chain``, ``sorted`` y ``warnings``. No
toca el ORM, ni la base, ni ninguna dependencia de dominio; por eso su prueba
corre sin transaccion. Del tercer elemento del triple solo se pide que sepa
``union()``, asi que un ``frozenset`` cumple el contrato igual que el
recordset vacio que la fuente usa en su propia prueba.

Divergencia de mecanismo declarada — ninguna
=============================================

Se porta literal salvo el idioma de docstrings y comentarios. Los dos
metodos que la fuente conserva avisando —``remove`` e ``items``— se portan
**con su aviso**: retirarlos aqui adelantaria una retirada que la referencia
no ha hecho, y la prueba mide que el ``DeprecationWarning`` se emite.
"""
from __future__ import annotations

import itertools
import typing
import warnings

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from collections.abc import Set as AbstractSet

T = typing.TypeVar('T')


def _boundaries(
    intervals: Intervals[T] | Iterable[tuple[T, T, AbstractSet]],
    opening: str,
    closing: str,
) -> Iterator[tuple[T, str, AbstractSet]]:
    """Recorre las fronteras de los intervalos.

    Emite dos eventos por intervalo —apertura y cierre— y **descarta el
    intervalo vacio**: la guarda ``start < stop`` es lo que hace que un
    ``(7, 7)`` no llegue nunca al resultado.
    """
    for start, stop, recs in intervals:
        if start < stop:
            yield (start, opening, recs)
            yield (stop, closing, recs)


class Intervals(typing.Generic[T]):
    """Coleccion ordenada de intervalos disjuntos con registros asociados.

    Cada intervalo es un triple ``(inicio, fin, registros)``, donde
    ``registros`` es un recordset — o cualquier conjunto que sepa ``union()``.

    Por defecto los intervalos **adyacentes se fusionan**: ``(1, 3, a)`` y
    ``(3, 5, b)`` dan ``(1, 5, a | b)``. ``keep_distinct=True`` lo impide, y
    entonces solo se fusiona lo que **solapa**.
    """

    def __init__(
        self,
        intervals: Iterable[tuple[T, T, AbstractSet]] | None = None,
        *,
        keep_distinct: bool = False,
    ):
        self._items: list[tuple[T, T, AbstractSet]] = []
        self._keep_distinct = keep_distinct
        if intervals:
            # normaliza la representacion de los intervalos
            append = self._items.append
            starts: list[T] = []
            items: AbstractSet | None = None
            if self._keep_distinct:
                # ordenar por el valor SOLO deja que 'stop' preceda a 'start'
                # en un empate, que es lo que mantiene separado lo adyacente.
                boundaries = sorted(
                    _boundaries(sorted(intervals), 'start', 'stop'),
                    key=lambda i: i[0])
            else:
                boundaries = sorted(_boundaries(intervals, 'start', 'stop'))
            for value, flag, value_items in boundaries:
                if flag == 'start':
                    starts.append(value)
                    if items is None:
                        items = value_items
                    else:
                        items = items.union(value_items)
                else:
                    start = starts.pop()
                    if not starts:
                        append((start, value, items))
                        items = None

    def __bool__(self):
        return bool(self._items)

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def __reversed__(self):
        return reversed(self._items)

    def __or__(self, other):
        """Devuelve la union de los dos conjuntos de intervalos."""
        return Intervals(
            itertools.chain(self._items, other._items),
            keep_distinct=self._keep_distinct)

    def __and__(self, other):
        """Devuelve la interseccion de los dos conjuntos de intervalos."""
        return self._merge(other, False)

    def __sub__(self, other):
        """Devuelve la diferencia de los dos conjuntos de intervalos."""
        return self._merge(other, True)

    def _merge(
        self,
        other: Intervals | Iterable[tuple[T, T, AbstractSet]],
        difference: bool,
    ) -> Intervals:
        """Diferencia o interseccion de los dos conjuntos de intervalos.

        La bandera ``keep_distinct`` del resultado es la del operando
        **izquierdo**: quien pide la operacion decide como se fusiona.
        """
        result = Intervals(keep_distinct=self._keep_distinct)
        append = result._items.append

        # usar 'self' y 'other' aqui abajo fuerza la normalizacion
        bounds1 = _boundaries(self, 'start', 'stop')
        bounds2 = _boundaries(
            Intervals(other, keep_distinct=self._keep_distinct),
            'switch', 'switch')

        start = None                    # lo fija start/stop
        recs1 = None                    # lo fija start
        enabled = difference            # lo cambia switch
        if self._keep_distinct:
            bounds = sorted(
                itertools.chain(bounds1, bounds2), key=lambda i: i[0])
        else:
            bounds = sorted(itertools.chain(bounds1, bounds2))
        for value, flag, recs in bounds:
            if flag == 'start':
                start = value
                recs1 = recs
            elif flag == 'stop':
                if enabled and start < value:
                    append((start, value, recs1))
                start = None
            else:
                if not enabled and start is not None:
                    start = value
                if enabled and start is not None and start < value:
                    append((start, value, recs1))
                enabled = not enabled

        return result

    def remove(self, interval):
        """Retira un intervalo del conjunto."""
        warnings.warn(
            "Deprecated since 19.0, do not mutate intervals",
            DeprecationWarning)
        self._items.remove(interval)

    def items(self):
        """Devuelve los intervalos."""
        warnings.warn(
            "Deprecated since 19.0, just iterate over Intervals",
            DeprecationWarning)
        return self._items


def intervals_overlap(interval_a: tuple[T, T], interval_b: tuple[T, T]) -> bool:
    """Dice si dos intervalos se cruzan.

    :param interval_a: el primer par ``(inicio, fin)``
    :param interval_b: el segundo par ``(inicio, fin)``
    :return: ``True`` si dos intervalos no vacios solapan
    """
    start_a, stop_a = interval_a
    start_b, stop_b = interval_b
    return start_a < stop_b and stop_a > start_b


def invert_intervals(
    intervals: Iterable[tuple[T, T]],
    first_start: T,
    last_stop: T,
) -> list[tuple[T, T]]:
    """Devuelve los huecos que quedan entre los intervalos recibidos.

    El caso de uso previsto es convertir «los intervalos disponibles» en «los
    intervalos no disponibles».

    :examples:
    ([(1, 2), (4, 5)], 0, 10) -> [(0, 1), (2, 4), (5, 10)]

    :param intervals: los intervalos ocupados, en cualquier orden
    :param first_start: inicio del intervalo total
    :param last_stop: fin del intervalo total
    """
    items = []
    prev_stop = first_start
    for start, stop in sorted(intervals):
        if start > last_stop:
            break
        if prev_stop < start:
            items.append((prev_stop, start))
        prev_stop = max(prev_stop, stop)
        if stop >= last_stop:
            break
    if prev_stop < last_stop:
        items.append((prev_stop, last_stop))
    # se aprovecha Intervals para fusionar lo contiguo
    return [
        (start, stop)
        for start, stop, _ in Intervals(
            [(start, stop, set()) for start, stop in items])
    ]
