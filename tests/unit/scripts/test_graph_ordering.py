"""La secuencia por niveles, medida por conducta y no por su nombre.

Estos tests son **puros**: no tocan Django ni la base. Miden el instrumento
sobre grafos cuyo desenlace se conoce de antemano.

El control que discrimina es
``test_a_cycle_is_reported_apart_and_never_ordered``: un recorrido en
profundidad que emita todo lo que visita publicaria los tres nodos del
ciclo con un orden inventado, y nadie podria distinguirlo de uno real.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))

from graph_ordering import topological_levels  # noqa: E402


class TestTopologicalLevels:
    """Kahn por niveles — su estado ES la respuesta que se busca."""

    def test_each_level_holds_what_no_longer_blocks(self):
        nodes = ['base', 'medio', 'hoja', 'suelto']
        edges = {'base': set(), 'medio': {'base'},
                 'hoja': {'medio'}, 'suelto': set()}
        levels, trapped = topological_levels(nodes, edges)
        assert levels == [['base', 'suelto'], ['medio'], ['hoja']]
        assert trapped == []

    def test_a_cycle_is_reported_apart_and_never_ordered(self):
        """EL CONTROL. Un ciclo no tiene orden interno; fingir uno miente.

        Si alguien cambiara Kahn por un recorrido en profundidad que emite
        todo lo que visita, los tres del ciclo apareceria­n en los niveles
        con un orden inventado y este test caeria.
        """
        nodes = ['libre', 'a', 'b', 'c']
        edges = {'libre': set(), 'a': {'b'}, 'b': {'c'}, 'c': {'a'}}
        levels, trapped = topological_levels(nodes, edges)
        assert levels == [['libre']]
        assert trapped == ['a', 'b', 'c']

    def test_an_edge_outside_the_node_set_does_not_block(self):
        """Una arista hacia fuera del universo medido no cuenta como bloqueo.

        Es el caso del porte: un simbolo de ``odoo/orm`` puede depender de
        uno de ``odoo/tools``, que no esta en el grafo. Contarlo dejaria el
        nodo bloqueado para siempre y lo publicaria como atrapado en ciclo.
        """
        levels, trapped = topological_levels(['a'], {'a': {'fuera'}})
        assert levels == [['a']]
        assert trapped == []
