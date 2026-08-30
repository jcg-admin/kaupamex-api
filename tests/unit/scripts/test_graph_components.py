"""Los ciclos de un grafo, medidos por conducta y no por su nombre.

Estos tests son **puros**: no tocan Django ni la base. Miden el instrumento
sobre grafos cuyo desenlace se conoce de antemano.

El control que discrimina es ``test_a_self_loop_is_a_cycle``: filtrar
solo por ``len(c) > 1`` —que es lo que el gate de addons hacia en su
cuerpo— lo dejaria pasar en silencio, y ese verde no distingue «no hay
ciclo» de «el instrumento no ve este ciclo».
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))

from graph_components import cyclic_components, strongly_connected_components  # noqa: E402


class TestStronglyConnectedComponents:
    """Tarjan — los grupos que se alcanzan mutuamente."""

    def test_a_chain_gives_one_component_per_node(self):
        nodes = ['a', 'b', 'c']
        edges = {'a': {'b'}, 'b': {'c'}, 'c': set()}
        components = strongly_connected_components(nodes, edges)
        assert sorted(sorted(c) for c in components) == [['a'], ['b'], ['c']]

    def test_a_cycle_of_three_gives_one_component_of_three(self):
        nodes = ['a', 'b', 'c']
        edges = {'a': {'b'}, 'b': {'c'}, 'c': {'a'}}
        components = strongly_connected_components(nodes, edges)
        assert len(components) == 1
        assert sorted(components[0]) == ['a', 'b', 'c']

    def test_it_does_not_recurse_on_a_long_chain(self):
        """Mil nodos en fila: el recorrido es iterativo, no recursivo.

        Con Tarjan recursivo esto levantaria ``RecursionError`` — el limite
        por defecto de Python es 1000. Es la razon medida por la que se
        extrajo la version iterativa que ``check_addon_cycles`` ya tenia en
        vez de escribir una nueva.
        """
        nodes = [str(n) for n in range(2000)]
        edges = {str(n): {str(n + 1)} for n in range(1999)}
        edges['1999'] = set()
        assert len(strongly_connected_components(nodes, edges)) == 2000


class TestCyclicComponents:
    """Solo los ciclos reales — un nodo suelto no lo es."""

    def test_isolated_nodes_are_not_cycles(self):
        assert cyclic_components(['a', 'b'], {'a': {'b'}, 'b': set()}) == []

    def test_a_self_loop_is_a_cycle(self):
        """Un componente de un nodo SI es ciclo cuando se apunta a si mismo.

        Filtrar solo por ``len(c) > 1`` lo dejaria pasar en silencio, que es
        exactamente un verde que no discrimina.
        """
        components = cyclic_components(['a'], {'a': {'a'}})
        assert [sorted(c) for c in components] == [['a']]
